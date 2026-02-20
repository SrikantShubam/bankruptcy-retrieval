import asyncio
import json
import logging
import os
from datetime import datetime, timezone
import random

from camoufox.async_api import AsyncCamoufox

from shared.gatekeeper import LLMGatekeeper
from shared.telemetry import TelemetryLogger
from config import EXCLUDED_SET
from session_manager import (
    launch_browser,
    get_or_create_page,
    session_health_check,
    save_cookies
)
from scout import scout_with_fallback
from fetcher import download_via_browser, download_via_httpx_fallback

# Disable noisy logging
logging.getLogger("asyncio").setLevel(logging.WARNING)

logger = TelemetryLogger(
    worktree="B",
    ground_truth_path="../bankruptcy-retrieval/data/ground_truth.json",
    log_dir="./logs",
)
gatekeeper = LLMGatekeeper()

async def pipeline_run():
    # Load deals dataset
    matches = 0
    with open('../bankruptcy-retrieval/data/deals_dataset.json', 'r') as f:
        deals = json.load(f)

    # 1. 5-Deal Exclusion Logic - ZERO API / Browser calls for these
    active_deals = []
    
    # Simulating time relative to overall run for elapsed_seconds
    start_time = datetime.now(timezone.utc)
    
    for deal in deals:
        if deal["company_name"] in EXCLUDED_SET or deal.get("already_processed"):
            # Emit log directly to the telemetry system
            logger.log_exclusion_skip(deal)
            continue
            
        active_deals.append(deal)

    if not active_deals:
        print("No active deals found.")
        return

    # 2. Launch single Camoufox instance
    try:
        browser = await launch_browser()
    except Exception as e:
        print(f"Failed to launch browser: {e}")
        return

    deals_processed = 0

    try:
        # Sequential processing - not concurrent per README
        for i, deal in enumerate(active_deals):
            logger.start_deal(deal["deal_id"])
            print(f"Processing deal {i+1}/{len(active_deals)}: {deal['company_name']}")
            
            # 3. Session Health Check every 10 deals
            if deals_processed > 0 and deals_processed % 10 == 0:
                print(f"Running health check at deal {deals_processed}...")
                browser, status = await session_health_check(browser, deals_processed)

            # 4. Scout for Candidate Documents
            candidates = await scout_with_fallback(browser, deal)
            
            # Emit scout telemetry
            logger.log_scout_query(
                deal=deal,
                source=candidates[0]["source"] if candidates else deal.get("claims_agent", "unknown"),
                query_params={"company_name": deal["company_name"]},
                results_count=len(candidates),
                api_calls_this_query=1 if candidates else 0
            )

            pipeline_status = "NOT_FOUND"
            local_file_path = None
            total_llm_calls = 0
            
            # 5. Gatekeeper Evaluation (Max 3 calls per deal)
            download_candidate = None
            for idx, candidate in enumerate(candidates[:3]):
                total_llm_calls += 1
                verdict, score, reasoning, token_cnt = await gatekeeper.evaluate(candidate)
                
                logger.log_gatekeeper_decision(
                    deal=deal,
                    docket_title=candidate["docket_title"],
                    attachment_descriptions=candidate["attachment_descriptions"],
                    llm_model="meta/llama-3.1-8b-instruct",
                    verdict=verdict,
                    score=score,
                    reasoning=reasoning,
                    token_count=token_cnt
                )
                
                if verdict == "DOWNLOAD":
                    download_candidate = candidate
                    break

            # 6. Fetcher download
            if download_candidate:
                pdf_url = download_candidate.get("resolved_pdf_url")
                
                # Fetch
                page = await get_or_create_page(browser)
                
                # We need to navigate to the source page potentially, but download_via_browser uses JS injection.
                fetch_res = await download_via_browser(page, pdf_url, deal["deal_id"])
                
                # If fail, try httpx fallback
                if not fetch_res["success"]:
                    context_cookies = await browser.contexts[0].cookies() if browser.contexts else []
                    fetch_res = await download_via_httpx_fallback(pdf_url, deal["deal_id"], context_cookies)

                logger.log_fetch_result(
                    deal=deal,
                    success=fetch_res["success"],
                    local_file_path=fetch_res["local_file_path"],
                    file_size_bytes=fetch_res["file_size_bytes"],
                    fetch_method=fetch_res["fetch_method"],
                    bot_bypass_used=True, # Implicit for Worktree B
                    failure_reason=fetch_res["failure_reason"]
                )
                
                if fetch_res["success"]:
                    pipeline_status = "DOWNLOADED"
                    local_file_path = fetch_res["local_file_path"]
                    
                    # Persist cookies
                    if browser.contexts:
                        await save_cookies(browser.contexts[0])
                else:
                    pipeline_status = "FETCH_FAILED"

            elif candidates:
                pipeline_status = "SKIPPED"

            # 7. Final Pipeline Terminal Telemetry
            logger.log_pipeline_terminal(
                deal=deal,
                pipeline_status=pipeline_status,
                total_api_calls=1,  # Browser action
                total_llm_calls=total_llm_calls,
                downloaded_file=local_file_path
            )

            deals_processed += 1
            
            # Sleep slightly between deals
            await asyncio.sleep(random.uniform(2.0, 4.0))

        # Output final benchmark
        logger.finalise()

    except KeyboardInterrupt:
        print("Pipeline interrupted by user.")
    except Exception as e:
        print(f"Pipeline crashed: {e}")
    finally:
        if browser:
            if hasattr(browser, "_camoufox_ctx"):
                await browser._camoufox_ctx.__aexit__(None, None, None)
            else:
                await browser.close()
        print("Pipeline complete. Browser closed.")

if __name__ == "__main__":
    asyncio.run(pipeline_run())
