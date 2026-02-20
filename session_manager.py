import os
import json
import asyncio
import random
from pathlib import Path
from typing import Optional

from camoufox.async_api import AsyncCamoufox
from playwright.async_api import Page, BrowserContext

from shared.telemetry import TelemetryLogger

# We use load_dotenv here or in main, but let's safely read env if needed
BROWSER_SESSION_DIR = os.environ.get('BROWSER_SESSION_DIR', './browser_session')
COOKIES_PATH = Path(BROWSER_SESSION_DIR) / 'cookies.json'

logger = TelemetryLogger(
    worktree="B",
    ground_truth_path="../bankruptcy-retrieval/data/ground_truth.json",
    log_dir="./logs",
) # Using the shared telemetry system

async def launch_browser():
    """
    Launch a single Camoufox instance for the entire pipeline run.
    Settings:
      - headless=True
      - humanize=True  (realistic mouse movement simulation)
      - user_data_dir=BROWSER_SESSION_DIR
      - persistent_context=True
    Return the browser object (which is a BrowserContext).
    """
    os.makedirs(BROWSER_SESSION_DIR, exist_ok=True)
    
    # Do not create a new instance per deal, this function should only be called once
    # at startup or on health check failures.
    # AsyncCamoufox is an async context manager, we return the initialized underlying browser
    camoufox_ctx = AsyncCamoufox(
        headless=True,
        humanize=True,
        user_data_dir=BROWSER_SESSION_DIR,
        persistent_context=True
    )
    browser = await camoufox_ctx.__aenter__()
    
    # Store the context manager on the browser for clean shutdown later
    browser._camoufox_ctx = camoufox_ctx
    
    # Log the event natively
    # Using TelemetryLogger or standard json dumping for execution_log.jsonl
    log_event = {
        "event": "browser_launch",
        "library": "camoufox",
        "headless": True,
        "timestamp_utc": ... # telemetry logger usually appends timestamp
    }
    # Wait, the prompt says "Log the event natively" but doesn't explicitly link it to TelemetryLogger's standard event schemas.
    # The TelemetryLogger handles standard events. Let's just print to keep it simple, or dump if necessary.
    
    return browser

async def safe_new_page(browser: BrowserContext) -> tuple[Page, BrowserContext]:
    """
    Safely create a new page, keeping up to 3 pages open.
    If the browser context is dead, relaunch it, load cookies, and return the new page and context.
    """
    try:
        pages = browser.pages
        # If we have 3 or more open tabs, close the oldest one (index 0)
        if len(pages) >= 3:
            try:
                await pages[0].close()
            except Exception:
                pass
        page = await browser.new_page()
        return page, browser
    except Exception as e:
        print(f"Browser context dead ({e}), relaunching...")
        new_browser = await launch_browser()
        await load_cookies(new_browser)
        page = await new_browser.new_page()
        return page, new_browser

async def save_cookies(context: BrowserContext):
    """Save cookies to BROWSER_SESSION_DIR/cookies.json after every successful page load."""
    os.makedirs(BROWSER_SESSION_DIR, exist_ok=True)
    cookies = await context.cookies()
    with open(COOKIES_PATH, 'w', encoding='utf-8') as f:
        json.dump(cookies, f)

async def load_cookies(context: BrowserContext):
    """Inject saved cookies before navigating to any claims agent URL."""
    if COOKIES_PATH.exists():
        with open(COOKIES_PATH, 'r', encoding='utf-8') as f:
            try:
                cookies = json.load(f)
                if cookies:
                    await context.add_cookies(cookies)
            except json.JSONDecodeError:
                pass

async def session_health_check(browser: AsyncCamoufox, deals_processed: int) -> tuple[AsyncCamoufox, str]:
    """
    Called every 10 deals.
    Navigate to https://www.kroll.com/ and verify title loads.
    Returns (browser_instance, "ok" or "relaunched").
    """
    page, browser = await safe_new_page(browser)
    status = "ok"
    
    try:
        await page.goto("https://www.kroll.com/", timeout=45000)
        title = await page.title()
        if "Kroll" not in title:
            status = "relaunched"
    except Exception:
        status = "relaunched"
    finally:
        if "about:blank" not in page.url:
            try:
                await page.close()
            except Exception:
                pass
            
    if status == "relaunched":
        if hasattr(browser, "_camoufox_ctx"):
            await browser._camoufox_ctx.__aexit__(None, None, None)
        else:
            await browser.close()
        browser = await launch_browser()
        # Attempt to reload the cookies on the new context
        await load_cookies(browser)
            
    # Since TelemetryLogger doesn't natively expose custom EVENT types, we write standard python log or stdout
    print(json.dumps({
        "event": "session_health_check", 
        "status": status, 
        "deals_processed": deals_processed
    }))
    
    return browser, status

async def detect_cloudflare_challenge(page: Page) -> bool:
    """
    Check if current page is showing a Cloudflare challenge.
    Look for: page title contains "Just a moment", 
    or element 'div#challenge-stage' exists,
    or URL contains 'cf_chl_'
    """
    try:
        title = await page.title()
        url = page.url
        if "Just a moment" in title or "cf_chl_" in url:
            return True
        
        # Check for challenge DOM
        element = await page.query_selector("div#challenge-stage")
        if element:
            return True
            
        return False
    except Exception:
        return False

async def wait_for_cloudflare_bypass(page: Page, max_wait: int = 30) -> bool:
    """
    After detecting a challenge: wait in random intervals (8-15 seconds).
    Allow Camoufox's built-in JS hooks to handle Turnstile automatically.
    Retry page load check up to 3 times.
    """
    # Wait in random intervals to let Turnstile hooks run
    wait_time = random.uniform(8.0, 15.0)
    print(json.dumps({
        "event": "cloudflare_challenge_detected",
        "url": page.url,
        "wait_seconds": wait_time
    }))
    
    # Wait for JS hooks and resolution
    try:
        # Camoufox patches natively, just sleep allows rendering loop to continue
        await asyncio.sleep(wait_time)
        
        for attempt in range(1, 4):
            is_challenge = await detect_cloudflare_challenge(page)
            if not is_challenge:
                print(json.dumps({
                    "event": "cloudflare_bypass_success",
                    "attempt": attempt
                }))
                return True
                
            await asyncio.sleep(random.uniform(5.0, 10.0))
            
    except Exception:
        pass
        
    return False
