import os
import json
import random
import asyncio
import asyncio
from typing import List, Dict, Any, Tuple
from camoufox.async_api import AsyncCamoufox
from playwright.async_api import Page, TimeoutError, BrowserContext

from shared.telemetry import TelemetryLogger
from session_manager import (
    safe_new_page,
    detect_cloudflare_challenge,
    wait_for_cloudflare_bypass
)
from config import KROLL_SELECTORS, STRETTO_SELECTORS, EPIQ_SELECTORS, EXCLUDED_SET

logger = TelemetryLogger(
    worktree="B",
    ground_truth_path="../bankruptcy-retrieval/data/ground_truth.json",
    log_dir="./logs",
)

async def extract_metadata_from_row(row_element, docket_title_selector: str, date_selector: str = None) -> Dict[str, Any]:
    """
    Extracts purely metadata from the DOM element before downloading.
    """
    try:
        title_el = await row_element.query_selector(docket_title_selector)
        docket_title = await title_el.inner_text() if title_el else "Unknown Title"
        
        filing_date = None
        if date_selector:
            date_el = await row_element.query_selector(date_selector)
            filing_date = await date_el.inner_text() if date_el else None
        
        pdf_link_el = await row_element.query_selector("a[href*='.pdf']")
        pdf_url = await pdf_link_el.get_attribute("href") if pdf_link_el else None
        
        return {
            "docket_title": docket_title.strip(),
            "filing_date": filing_date.strip() if filing_date else None,
            "resolved_pdf_url": pdf_url, 
            "attachment_descriptions": []  # Empty as per instruction if not available directly
        }
    except Exception:
        return {}

async def scout_kroll(page: Page, company_name: str, filing_year: int) -> List[Dict[str, Any]]:
    """Navigate Kroll, search for case, extract document metadata."""
    results = []
    deal_id = company_name.lower().replace(" ", "-").replace(",", "").replace(".", "")
    
    try:
        url = f"https://www.kroll.com/en/services/restructuring/cases/{deal_id}"
        response = await page.goto(url, timeout=45000)
        
        if response and response.status == 404:
            await page.goto("https://www.kroll.com/en/services/restructuring/cases", timeout=45000)
            
            if await detect_cloudflare_challenge(page):
                bypassed = await wait_for_cloudflare_bypass(page)
                if not bypassed:
                    return []

            await page.wait_for_load_state("networkidle", timeout=30000)
            
            selectors_to_try = [
                "input[aria-label*='case' i]",
                "input[aria-label*='search' i][aria-label*='case' i]", 
                "input#case-search",
                "input[name*='case']",
                ".case-search input",
                ".restructuring-search input",
            ]
            
            for selector in selectors_to_try:
                element = page.locator(selector).first
                if await element.is_visible():
                    await element.click()
                    for char in company_name:
                        await page.keyboard.type(char)
                        await asyncio.sleep(random.uniform(0.08, 0.15))
                    break
            else:
                await page.screenshot(path=f"debug_kroll_{deal_id}.png")
                raise ValueError(f"Could not find Kroll case search input for {company_name}")

            # Wait for results and click first match
            try:
                case_results = await page.wait_for_selector(KROLL_SELECTORS["case_result"], timeout=10000)
                await case_results.click()
            except TimeoutError:
                return [] # Not found
            
        # On case page, wait for document table
        await page.wait_for_selector(KROLL_SELECTORS["document_table_rows"], timeout=15000)
        rows = await page.query_selector_all(KROLL_SELECTORS["document_table_rows"])
        
        for row in rows:
            # Check text for First Day or DIP
            text = await row.inner_text()
            text_lower = text.lower()
            if "first day" in text_lower or "dip motion" in text_lower or "capital structure" in text_lower:
                meta = await extract_metadata_from_row(row, "td:nth-child(3)", "td:nth-child(1)")
                if meta.get("resolved_pdf_url"):
                    # Kroll links might be relative
                    url = meta["resolved_pdf_url"]
                    if url.startswith("/"):
                        url = f"https://cases.ra.kroll.com{url}"
                    meta["resolved_pdf_url"] = url
                    meta["source"] = "kroll"
                    results.append(meta)
                    
    except Exception as e:
        await page.screenshot(path=f"debug_kroll_fail_{deal_id}.png")
        print(f"Kroll Scout Error: {e}")
        
    return results

async def scout_stretto(page: Page, company_name: str, filing_year: int) -> List[Dict[str, Any]]:
    """Try direct URL slug first, fall back to search UI."""
    results = []
    slug = company_name.lower().replace(" ", "-").replace(",", "").replace(".", "")
    
    try:
        # Try direct navigation
        url = f"https://cases.stretto.com/{slug}/"
        response = await page.goto(url, timeout=30000)
        
        if response and response.status == 404:
            # Fallback to search
            url = f"https://cases.stretto.com/?s={company_name}"
            await page.goto(url, timeout=30000)
            
            # Click first result if available (simplified for now)
            # Would need exact Stretto search result DOM structure here
            # Assuming it routes to the slug page eventually
            
        if await detect_cloudflare_challenge(page):
            await wait_for_cloudflare_bypass(page)

        # We are on the case page now, look for documents
        await page.wait_for_selector(STRETTO_SELECTORS["document_section"], timeout=15000)
        doc_links = await page.query_selector_all(STRETTO_SELECTORS["pdf_links"])
        
        for link in doc_links:
            text = await link.inner_text()
            text_lower = text.lower()
            if "first day" in text_lower or "dip motion" in text_lower:
                pdf_url = await link.get_attribute("href")
                results.append({
                    "docket_title": text.strip(),
                    "filing_date": None,  # Often not easily row-aligned in Stretto
                    "resolved_pdf_url": pdf_url,
                    "attachment_descriptions": [],
                    "source": "stretto"
                })
    except Exception as e:
        print(f"Stretto Scout Error: {e}")
        
    return results

async def scout_epiq(page: Page, company_name: str, filing_year: int) -> List[Dict[str, Any]]:
    """Navigate Epiq docket. (nodriver fallback handled in orchestrator)"""
    results = []
    
    try:
        # Epiq URLs often require the exact case name slug or search
        await page.goto("https://dm.epiq11.com", timeout=45000)
        
        if await detect_cloudflare_challenge(page):
            bypassed = await wait_for_cloudflare_bypass(page)
            if not bypassed:
                raise Exception("Cloudflare blocked Epiq")
                
        search_input = await page.wait_for_selector(EPIQ_SELECTORS["search_input"], timeout=15000)
        await search_input.click()
        for char in company_name:
            await page.keyboard.type(char)
            await asyncio.sleep(random.uniform(0.08, 0.15))
            
        await page.keyboard.press("Enter")
        await asyncio.sleep(5) # Wait for page load
        
        # In a real scenario, we'd navigate to the docket tab. Let's assume we find rows.
        rows = await page.query_selector_all(EPIQ_SELECTORS["docket_rows"])
        for row in rows:
            text = await row.inner_text()
            text_lower = text.lower()
            if "first day" in text_lower or "dip motion" in text_lower:
                meta = await extract_metadata_from_row(row, "td.title", "td.date")
                if meta.get("resolved_pdf_url"):
                    meta["resolved_pdf_url"] = f"https://dm.epiq11.com{meta['resolved_pdf_url']}"
                    meta["source"] = "epiq"
                    results.append(meta)
                    
    except Exception as e:
        print(f"Epiq Scout Error: {e}")
        raise e # Re-raise for nodriver fallback detection
        
    return results

# nodriver fallback logic for Epiq
async def scout_epiq_nodriver_fallback(company_name: str) -> List[Dict[str, Any]]:
    import nodriver as uc
    browser = await uc.start(headless=True)
    results = []
    try:
        page = await browser.get('https://dm.epiq11.com')
        await asyncio.sleep(15) # Wait for possible Turnstile
        
        # Basic nodriver interaction (simplified)
        search = await page.select(EPIQ_SELECTORS["search_input"])
        if search:
            await search.send_keys(company_name)
            await search.send_keys('\n')
            await asyncio.sleep(5)
            
            # Extract links using JS evaluation since nodriver DOM is node-based
            links = await page.evaluate('''() => {
                let items = [];
                document.querySelectorAll("a[href*='.pdf']").forEach(a => {
                    if(a.innerText.toLowerCase().includes('first day')) {
                        items.push({title: a.innerText, url: a.href});
                    }
                });
                return items;
            }''')
            
            for item in links:
                results.append({
                    "docket_title": item["title"],
                    "filing_date": None,
                    "resolved_pdf_url": item["url"],
                    "attachment_descriptions": [],
                    "source": "epiq"
                })
    except Exception as e:
        print(f"nodriver Epiq Error: {e}")
    finally:
        browser.stop()
        
    return results

async def scout_with_fallback(browser: BrowserContext, deal: Dict[str, Any]) -> Tuple[List[Dict[str, Any]], BrowserContext]:
    """
    Orchestrates the fallback cascade:
    1. Try claims agent browser (Camoufox)
    2. If blocked after 3 attempts: try CourtListener RECAP API (fallback)
    3. If RECAP also fails: return empty list
    """
    company_name = deal["company_name"]
    filing_year = deal["filing_year"]
    claims_agent = deal.get("claims_agent", "").lower()
    
    page, browser = await safe_new_page(browser)
    results = []
    
    # 1. Claims Agent Switch
    if claims_agent == "kroll":
        results = await scout_kroll(page, company_name, filing_year)
    elif claims_agent == "stretto":
        results = await scout_stretto(page, company_name, filing_year)
    elif claims_agent == "epiq":
        # Epiq has the nodriver fallback logic (2 attempts with Camoufox first)
        for attempt in range(2):
            try:
                results = await scout_epiq(page, company_name, filing_year)
                if results:
                    break
            except Exception:
                pass
                
        if not results:
            print("Falling back to nodriver for Epiq...")
            results = await scout_epiq_nodriver_fallback(company_name)
            
    # Do NOT close tab, safe_new_page keeps 3 tabs limit and closing inside exception loop crashes Playwright
            
    # 2. CourtListener RECAP API Fallback (mocked for Worktree B specific scope)
    if not results:
        print(json.dumps({
            "event": "fallback_triggered", 
            "reason": "CLAIMS_AGENT_BLOCKED", 
            "fallback": "courtlistener", 
            "deal_id": deal["deal_id"]
        }))
        # API fallback logic would go here. We simulate returning an empty list to proceed to Not Found
        pass
        
    # Standardize output for Gatekeeper
    for r in results:
        r["deal_id"] = deal["deal_id"]
        r["api_calls_consumed"] = 1 # Approximating browser action as 1 call metric
        
    return results, browser
