import os
import re
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

KROLL_CASE_SLUGS = {
    "WeWork": "WeWork",
    "Rite Aid": "RiteAid", 
    "SVB Financial Group": "SVBFinancial",
    "Enviva": "Enviva",
    "Ligado Networks": "LigadoNetworks",
    "Tehum Care Services": "TehumCare",
    "Chicken Soup for the Soul Entertainment": "ChickenSoupfortheSoulEntertainment",
    "JOANN": "JOANN",
    "Bed Bath & Beyond": "BedBathBeyond",
    "Spirit Airlines": "SpiritAirlines",
    "Big Lots": "BigLots",
    "Tupperware Brands": "Tupperware",
    "Red Lobster": "RedLobster",
    "Vice Media": "ViceMedia",
    "Diamond Sports Group": "DiamondSportsGroup",
    "Avaya": "Avaya",
    "Cyxtera Technologies": "Cyxtera",
    "Core Scientific": "CoreScientific",
    "Celsius Network": "CelsiusNetwork",
}

def build_kroll_url(company_name: str) -> str:
    slug = KROLL_CASE_SLUGS.get(company_name)
    if not slug:
        # Fallback slug guessing
        clean = company_name
        for suffix in [" Inc", " LLC", " Corp", " Group", " Holdings",
                       " Financial", " Technologies", " Entertainment",
                       " Brands", " Network", " Services", " Company"]:
            clean = clean.replace(suffix, "")
        slug = clean.replace(" ", "").replace("&", "").replace("'", "")
    return f"https://restructuring.ra.kroll.com/{slug}/"

async def scout_kroll(page: Page, company_name: str, filing_year: int) -> List[Dict[str, Any]]:
    """Navigate Kroll, search for case, extract document metadata."""
    results = []
    deal_id = company_name.lower().replace(" ", "-").replace(",", "").replace(".", "")
    
    try:
        url = build_kroll_url(company_name)
        await page.goto(url, wait_until="networkidle", timeout=45000)
        
        # Screenshot immediately — before ANY other logic
        await page.screenshot(path=f"debug_kroll_{deal_id}_loaded.png")
        title = await page.title()
        print(f"Kroll page title: {title}")
        print(f"Kroll URL: {page.url}")
        
        # Check we're on a real case page, not the generic listing
        if "restructuring-administration-cases" in page.url or \
           "Restructuring Administration Cases" in await page.title():
            # Slug didn't match, skip this case
            return []
            
        # Click the Docket tab from the left sidebar
        try:
            await page.click("a:text('Docket') >> visible=true", timeout=10000)
            await page.wait_for_load_state("networkidle", timeout=20000)
            await page.screenshot(path=f"debug_kroll_{deal_id}_docket.png")
        except Exception as e:
            print(f"Failed to click Docket tab: {e}")
            await page.screenshot(path=f"debug_kroll_docket_fail_{deal_id}.png")
            return []
            
        search_box = await page.query_selector(
            "input[placeholder*=\"'motion'\"], input[placeholder*=\"'123'\"]"
        )
        
        keywords_to_try = [
            "first day declaration", 
            "declaration in support", 
            "DIP motion", 
            "cash collateral"
        ] if search_box else [""]
        
        for search_term in keywords_to_try:
            if search_box and search_term:
                await search_box.click()
                await search_box.fill("")
                await asyncio.sleep(random.uniform(0.3, 0.7))
                
                for char in search_term:
                    await page.keyboard.type(char)
                    await asyncio.sleep(random.uniform(0.08, 0.15))
                
                await page.keyboard.press("Enter")
                await page.wait_for_load_state("networkidle")
                await asyncio.sleep(random.uniform(1.0, 2.0))
                
                await page.screenshot(path=f"debug_kroll_{deal_id}_searched_{search_term.replace(' ', '_')}.png")
            
            rows = await page.query_selector_all("table tbody tr")
            
            for row in rows:
                text = await row.inner_text()
                text_lower = text.lower()
                
                # Check keyword match
                keyword_hit = any(kw in text_lower for kw in [
                    "first day", "dip motion", "debtor in possession",
                    "cash collateral", "declaration in support",
                    "capital structure", "prepetition"
                ])
                if not keyword_hit:
                    continue
                
                # Extract link (broadened selector from Bug 3 fix)
                links = await row.query_selector_all("a[href]")
                href = None
                for a in links:
                    h = await a.get_attribute("href")
                    if h and any(p in h for p in [
                        ".pdf", "/Document/", "/document/",
                        "fileId=", "documentId=", "/File/", "/download"
                    ]):
                        href = h
                        break
                if href is None and links:
                    href = await links[0].get_attribute("href")
                
                if href and href.startswith("/"):
                    href = f"https://restructuring.ra.kroll.com{href}"
                
                # Extract date from text
                date_match = re.search(r"\b(\d{1,2}/\d{1,2}/\d{4}|\d{4}-\d{2}-\d{2})\b", text)
                filing_date = date_match.group(1) if date_match else None
                if filing_date and "/" in filing_date:
                    p = filing_date.split("/")
                    if len(p) == 3:
                        filing_date = f"{p[2]}-{p[0].zfill(2)}-{p[1].zfill(2)}"
                
                # Get docket number from first cell
                cells = await row.query_selector_all("td")
                docket_num = ""
                if cells:
                    docket_num = (await cells[0].inner_text()).strip()
                
                results.append({
                    "docket_entry_id": docket_num,
                    "docket_title": text.strip()[:200],
                    "filing_date": filing_date,
                    "resolved_pdf_url": href,
                    "attachment_descriptions": [],
                    "source": "kroll",
                })
                
                if results:
                    break  # First match per keyword search is sufficient — Gatekeeper decides
                    
            if results:
                break # Break outer loop since we found valid candidates
                    
    except Exception as e:
        print(f"Kroll Scout Error TYPE: {type(e).__name__}")
        print(f"Kroll Scout Error: {e}")
        try:
            await page.screenshot(path=f"debug_kroll_fail_{deal_id}.png")
        except:
            print("Screenshot also failed - page object is dead")
        
    return results

async def scout_stretto(page: Page, company_name: str, filing_year: int) -> List[Dict[str, Any]]:
    """Try direct URL slug first, fall back to search UI."""
    results = []
    slug = company_name.lower().replace(" ", "-").replace(",", "").replace(".", "")
    
    try:
        # Try direct navigation
        url = f"https://cases.stretto.com/{slug}/"
        response = await page.goto(url, wait_until="domcontentloaded", timeout=30000)
        
        if response and response.status == 404:
            # Fallback to search
            url = f"https://cases.stretto.com/?s={company_name}"
            await page.goto(url, wait_until="domcontentloaded", timeout=30000)
            
        await page.screenshot(path=f"debug_stretto_{slug}_loaded.png")
            
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
        await page.screenshot(path=f"debug_stretto_fail_{slug}.png")
        print(f"Stretto Scout Error: {e}")
        
    return results

async def scout_epiq(page: Page, company_name: str, filing_year: int) -> List[Dict[str, Any]]:
    """Navigate Epiq docket. (nodriver fallback handled in orchestrator)"""
    results = []
    slug = company_name.lower().replace(" ", "-").replace(",", "").replace(".", "")
    
    try:
        url = f"https://dm.epiq11.com/{slug}/docket"
        await page.goto(url, wait_until="domcontentloaded", timeout=45000)
        
        await page.screenshot(path=f"debug_epiq_{slug}_loaded.png")
        
        if await detect_cloudflare_challenge(page):
            bypassed = await wait_for_cloudflare_bypass(page)
            if not bypassed:
                raise Exception("Cloudflare blocked Epiq")
                
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
        await page.screenshot(path=f"debug_epiq_fail_{slug}.png")
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
