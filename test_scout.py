import asyncio
import json
from playwright.async_api import async_playwright
from camoufox.async_api import AsyncCamoufox
from session_manager import launch_browser
from scout import scout_with_fallback

async def main():
    browser = await launch_browser()
    deal = {
      "deal_id": "rite-aid-2023",
      "company_name": "Rite Aid",
      "filing_year": 2023,
      "claims_agent": "kroll",
      "petition_date": "2023-10-15"
    }
    results, browser = await scout_with_fallback(browser, deal)
    for r in results:
        print(f"Title: {r.get('docket_title')}")
        print(f"Date: {r.get('filing_date')}")
        print("---")
    await browser.close()

asyncio.run(main())
