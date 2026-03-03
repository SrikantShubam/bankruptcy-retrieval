"""
Main entrypoint for Worktree A - Pure CourtListener RECAP API Pipeline
"""
import asyncio
import json
import logging
import os
import sys
from typing import Dict, List, Any

# Add the shared directory to the path
sys.path.insert(0, '../bankruptcy-retrieval')

# Diagnostic test
import httpx
from shared.config import find_root_env
from dotenv import load_dotenv
load_dotenv(find_root_env())

async def test():
    token = os.environ.get("COURTLISTENER_API_TOKEN", "NOT_FOUND")
    print(f"Token loaded: {token[:15] if token != 'NOT_FOUND' else 'NOT_FOUND'}...")
    async with httpx.AsyncClient() as client:
        try:
            # Test with no parameters first
            print("Testing with no parameters...")
            r = await client.get(
                "https://www.courtlistener.com/api/rest/v4/dockets/",
                headers={"Authorization": f"Token {token}"},
                timeout=30.0
            )
            print(f"Status: {r.status_code}")
            print(f"Response: {r.text[:500]}")

            # Test with just q parameter
            print("\nTesting with q parameter...")
            r = await client.get(
                "https://www.courtlistener.com/api/rest/v4/dockets/",
                headers={"Authorization": f"Token {token}"},
                params={"q": "WeWork"},
                timeout=30.0
            )
            print(f"Status: {r.status_code}")
            print(f"Response: {r.text[:500]}")

            # Test with fields parameter only
            print("\nTesting with fields parameter...")
            r = await client.get(
                "https://www.courtlistener.com/api/rest/v4/dockets/",
                headers={"Authorization": f"Token {token}"},
                params={"fields": "id,case_name"},
                timeout=30.0
            )
            print(f"Status: {r.status_code}")
            print(f"Response: {r.text[:500]}")

        except Exception as e:
            print(f"Error during test: {e}")
            import traceback
            traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        asyncio.run(test())
        sys.exit(0)

# Import shared modules
from shared.config import (
    is_excluded,
    PRIORITY_KEYWORDS,
    MAX_KEYWORD_QUERIES_PER_DEAL
)
from shared.gatekeeper import LLMGatekeeper, CandidateDocument
from shared.telemetry import TelemetryLogger

# Import worktree-specific modules
from scout import (
    find_document_for_deal,
    close_http_client as close_scout_client,
    DailyBudgetExhausted
)
from fetcher import (
    download_recap_pdf,
    close_http_client as close_fetcher_client
)
from config import COURTLISTENER_API_TOKEN

# Set up logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

# Constants
DATASET_PATH = "../bankruptcy-retrieval/data/deals_dataset.json"
GROUND_TRUTH_PATH = "../bankruptcy-retrieval/data/ground_truth.json"
WORKTREE_NAME = "A"

# Standard test deals for quick validation
STANDARD_TEST_DEALS = [
    "wework-2023", "rite-aid-2023", "blockfi-2022",
    "bed-bath-beyond-2023", "yellow-corp-2023", "mitchells-butlers-2023",
    "kidoz-2023", "svb-financial-2023", "talen-energy-2023", "medical-decoy-c"
]

async def process_deal(deal: Dict[str, Any], gatekeeper: LLMGatekeeper, telemetry: TelemetryLogger) -> None:
    """
    Process a single deal through the pipeline: Scout → Gatekeeper → Fetcher

    Args:
        deal: Deal data from the dataset
        gatekeeper: LLM Gatekeeper instance
        telemetry: Telemetry logger instance
    """
    deal_id = deal.get("deal_id", "unknown")
    company_name = deal.get("company_name", "unknown")

    logger.info(f"Processing deal: {deal_id} ({company_name})")
    telemetry.start_deal(deal_id)

    # Check if deal should be excluded
    if is_excluded(deal):
        logger.info(f"Skipping excluded deal: {deal_id}")
        telemetry.log_exclusion_skip(deal)
        telemetry.log_pipeline_terminal(
            deal=deal,
            pipeline_status="ALREADY_PROCESSED",
            total_api_calls=0,
            total_llm_calls=0
        )
        return

    try:
        # Single-phase search using V4 API
        logger.info(f"Searching for document: {company_name}")
        candidate_data = await find_document_for_deal(
            company_name=company_name,
            filing_year=deal.get("filing_year", 2023),
            court=deal.get("court", "")
        )

        api_calls_consumed = candidate_data.get("api_calls_consumed", 0) if candidate_data else 0

        # Log the scout query
        telemetry.log_scout_query(
            deal=deal,
            source="courtlistener",
            query_params={
                "company_name": company_name,
                "filing_year": deal.get("filing_year", 2023),
                "court": deal.get("court", "")
            },
            results_count=1 if candidate_data else 0,
            api_calls_this_query=api_calls_consumed
        )

        if not candidate_data:
            logger.info(f"No relevant document found for: {deal_id}")
            telemetry.log_pipeline_terminal(
                deal=deal,
                pipeline_status="NOT_FOUND",
                total_api_calls=api_calls_consumed,
                total_llm_calls=0
            )
            return

        # Create candidate document for gatekeeper
        logger.info(f"Found document for: {deal_id}")
        candidate = CandidateDocument(
            deal_id=deal_id,
            source=candidate_data["source"],
            docket_entry_id=candidate_data["docket_entry_id"],
            docket_title=candidate_data["docket_title"],
            filing_date=candidate_data["filing_date"],
            attachment_descriptions=candidate_data["attachment_descriptions"],
            resolved_pdf_url=candidate_data["resolved_pdf_url"],
            api_calls_consumed=api_calls_consumed
        )

        # Gatekeeper evaluation
        logger.info(f"Evaluating with Gatekeeper: {deal_id}")
        gatekeeper_result = await gatekeeper.evaluate(candidate)

        # Log gatekeeper decision
        telemetry.log_gatekeeper_decision(
            deal=deal,
            docket_title=candidate_data["docket_title"],
            attachment_descriptions=candidate_data["attachment_descriptions"],
            llm_model=gatekeeper_result.model_used,
            verdict=gatekeeper_result.verdict,
            score=gatekeeper_result.score,
            reasoning=gatekeeper_result.reasoning,
            token_count=gatekeeper_result.token_count
        )

        if gatekeeper_result.verdict != "DOWNLOAD":
            logger.info(f"Gatekeeper rejected: {deal_id} (Score: {gatekeeper_result.score})")
            telemetry.log_pipeline_terminal(
                deal=deal,
                pipeline_status="SKIPPED",
                total_api_calls=api_calls_consumed,
                total_llm_calls=1
            )
            return

        # Fetch the PDF
        logger.info(f"Downloading PDF: {candidate_data['resolved_pdf_url']}")
        fetch_result = await download_recap_pdf(
            pdf_url=candidate_data["resolved_pdf_url"],
            deal_id=deal_id
        )

        # Log fetch result
        telemetry.log_fetch_result(
            deal=deal,
            success=fetch_result["success"],
            local_file_path=fetch_result["local_file_path"],
            file_size_bytes=fetch_result["size_bytes"],
            fetch_method="httpx_stream",
            bot_bypass_used=False,
            failure_reason=fetch_result["failure_reason"]
        )

        if not fetch_result["success"]:
            logger.info(f"Failed to download PDF: {deal_id}")
            telemetry.log_pipeline_terminal(
                deal=deal,
                pipeline_status="FETCH_FAILED",
                total_api_calls=api_calls_consumed,
                total_llm_calls=1
            )
            return

        # Success - document downloaded
        logger.info(f"Successfully downloaded PDF: {deal_id}")
        telemetry.log_pipeline_terminal(
            deal=deal,
            pipeline_status="DOWNLOADED",
            total_api_calls=api_calls_consumed,
            total_llm_calls=1,
            downloaded_file=fetch_result["local_file_path"]
        )

    except DailyBudgetExhausted:
        logger.error(f"Daily API budget exhausted. Stopping pipeline.")
        telemetry.log_pipeline_terminal(
            deal=deal,
            pipeline_status="NOT_FOUND",  # Treat as not found since we couldn't search
            total_api_calls=api_calls_consumed,
            total_llm_calls=0
        )
        raise
    except Exception as e:
        logger.error(f"Error processing deal {deal_id}: {str(e)}")
        import traceback
        traceback.print_exc()
        telemetry.log_pipeline_terminal(
            deal=deal,
            pipeline_status="NOT_FOUND",  # Treat as not found on error
            total_api_calls=api_calls_consumed,
            total_llm_calls=0
        )

async def main():
    """Main pipeline execution"""
    logger.info("Starting Worktree A - Pure CourtListener RECAP API Pipeline")

    # Check if API token is available
    if not COURTLISTENER_API_TOKEN:
        logger.error("COURTLISTENER_API_TOKEN not found in environment variables")
        return

    # Load dataset
    try:
        with open(DATASET_PATH, 'r') as f:
            all_deals = json.load(f)
        logger.info(f"Loaded {len(all_deals)} deals from dataset")
    except Exception as e:
        logger.error(f"Failed to load dataset: {str(e)}")
        return

    # Check for standard test flag
    if "--standard-test" in sys.argv:
        deals = [d for d in all_deals if d["deal_id"] in STANDARD_TEST_DEALS]
        deals.sort(key=lambda d: STANDARD_TEST_DEALS.index(d["deal_id"]) if d["deal_id"] in STANDARD_TEST_DEALS else len(STANDARD_TEST_DEALS))
        logger.info(f"Running standard test on {len(deals)} deals")
    else:
        deals = all_deals

    # Initialize telemetry
    telemetry = TelemetryLogger(
        worktree=WORKTREE_NAME,
        ground_truth_path=GROUND_TRUTH_PATH,
        log_dir="./logs"
    )

    # Initialize gatekeeper
    gatekeeper = LLMGatekeeper()

    # Process deals
    processed_count = 0
    for deal in deals:
        try:
            await process_deal(deal, gatekeeper, telemetry)
            processed_count += 1

            # Small delay to be respectful to the API
            await asyncio.sleep(0.1)

        except DailyBudgetExhausted:
            logger.error("Daily API budget exhausted. Stopping pipeline.")
            break
        except Exception as e:
            logger.error(f"Unexpected error processing deal {deal.get('deal_id', 'unknown')}: {str(e)}")
            # Continue with next deal

    # Finalize telemetry
    try:
        report = telemetry.finalise()
        logger.info("Pipeline completed successfully")
        telemetry.print_summary()
    except Exception as e:
        logger.error(f"Error finalizing telemetry: {str(e)}")

    # Close HTTP clients
    await close_scout_client()
    await close_fetcher_client()

    logger.info(f"Processed {processed_count} deals")

if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "--test":
        asyncio.run(test())
    else:
        asyncio.run(main())