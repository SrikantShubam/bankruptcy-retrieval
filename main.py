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
    find_docket,
    find_docket_entries,
    get_recap_document_metadata,
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

    # Initialize counters
    api_calls_for_deal = 0

    try:
        # Phase 1: Find docket
        logger.info(f"Searching for docket: {company_name}")
        docket = await find_docket(
            company_name=company_name,
            filing_year=deal.get("filing_year", 2023),
            court=deal.get("court", ""),
            client=None  # Using module-level client
        )
        api_calls_for_deal += 1

        # Log the scout query
        telemetry.log_scout_query(
            deal=deal,
            source="courtlistener",
            query_params={
                "case_name__icontains": company_name,
                "date_filed__gte": f"{deal.get('filing_year', 2023)}-01-01",
                "date_filed__lte": f"{deal.get('filing_year', 2023)}-12-31",
                "court": deal.get("court", ""),
                "chapter": 11
            },
            results_count=1 if docket else 0,
            api_calls_this_query=1
        )

        if not docket:
            logger.info(f"No docket found for: {deal_id}")
            telemetry.log_pipeline_terminal(
                deal=deal,
                pipeline_status="NOT_FOUND",
                total_api_calls=api_calls_for_deal,
                total_llm_calls=0
            )
            return

        docket_id = docket.get("id")
        logger.info(f"Found docket ID: {docket_id}")

        # Phase 2: Find docket entries with priority keywords
        logger.info(f"Searching for docket entries: {docket_id}")
        entries = await find_docket_entries(
            docket_id=docket_id,
            keywords=PRIORITY_KEYWORDS,
            client=None  # Using module-level client
        )

        # Count API calls made in find_docket_entries
        # We made one call per keyword (up to MAX_KEYWORD_QUERIES_PER_DEAL)
        keyword_queries_made = min(len(PRIORITY_KEYWORDS), MAX_KEYWORD_QUERIES_PER_DEAL)
        api_calls_for_deal += keyword_queries_made

        if not entries:
            logger.info(f"No relevant entries found for: {deal_id}")
            telemetry.log_pipeline_terminal(
                deal=deal,
                pipeline_status="NOT_FOUND",
                total_api_calls=api_calls_for_deal,
                total_llm_calls=0
            )
            return

        logger.info(f"Found {len(entries)} potential entries for: {deal_id}")

        # For simplicity, we'll process the first entry that has recap documents
        selected_entry = None
        for entry in entries:
            if entry.get("recap_documents"):
                selected_entry = entry
                break

        if not selected_entry:
            logger.info(f"No entries with recap documents for: {deal_id}")
            telemetry.log_pipeline_terminal(
                deal=deal,
                pipeline_status="NOT_FOUND",
                total_api_calls=api_calls_for_deal,
                total_llm_calls=0
            )
            return

        entry_id = selected_entry.get("id")
        entry_description = selected_entry.get("description", "")
        entry_date_filed = selected_entry.get("date_filed", "")

        # Get the first recap document
        recap_docs = selected_entry.get("recap_documents", [])
        if not recap_docs:
            logger.info(f"No recap documents found for entry: {entry_id}")
            telemetry.log_pipeline_terminal(
                deal=deal,
                pipeline_status="NOT_FOUND",
                total_api_calls=api_calls_for_deal,
                total_llm_calls=0
            )
            return

        recap_doc = recap_docs[0]
        recap_doc_id = recap_doc.get("id")

        # Phase 3: Get recap document metadata
        logger.info(f"Getting metadata for recap document: {recap_doc_id}")
        doc_metadata = await get_recap_document_metadata(
            doc_id=recap_doc_id,
            client=None  # Using module-level client
        )
        api_calls_for_deal += 1

        if not doc_metadata:
            logger.info(f"Failed to get metadata for recap document: {recap_doc_id}")
            telemetry.log_pipeline_terminal(
                deal=deal,
                pipeline_status="NOT_FOUND",
                total_api_calls=api_calls_for_deal,
                total_llm_calls=0
            )
            return

        doc_description = doc_metadata.get("description", "")
        filepath_local = doc_metadata.get("filepath_local")
        is_available = doc_metadata.get("is_available", False)

        # Construct the full PDF URL if available
        resolved_pdf_url = None
        if filepath_local:
            resolved_pdf_url = f"/recap/{filepath_local.lstrip('/')}" if not filepath_local.startswith("/recap/") else filepath_local

        # Phase 4: Gatekeeper evaluation
        logger.info(f"Evaluating with Gatekeeper: {entry_id}")
        candidate = CandidateDocument(
            deal_id=deal_id,
            source="courtlistener",
            docket_entry_id=str(entry_id),
            docket_title=entry_description,
            filing_date=entry_date_filed,
            attachment_descriptions=[doc_description] if doc_description else [],
            resolved_pdf_url=resolved_pdf_url,
            api_calls_consumed=api_calls_for_deal
        )

        gatekeeper_result = await gatekeeper.evaluate(candidate)

        # Log gatekeeper decision
        telemetry.log_gatekeeper_decision(
            deal=deal,
            docket_title=entry_description,
            attachment_descriptions=[doc_description] if doc_description else [],
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
                total_api_calls=api_calls_for_deal,
                total_llm_calls=1
            )
            return

        # Phase 5: Fetch the PDF
        logger.info(f"Downloading PDF: {resolved_pdf_url}")
        if not resolved_pdf_url or not is_available:
            logger.info(f"PDF not available in RECAP: {deal_id}")
            telemetry.log_fetch_result(
                deal=deal,
                success=False,
                local_file_path=None,
                file_size_bytes=None,
                fetch_method="httpx_stream",
                bot_bypass_used=False,
                failure_reason="not_in_recap"
            )
            telemetry.log_pipeline_terminal(
                deal=deal,
                pipeline_status="FETCH_FAILED",
                total_api_calls=api_calls_for_deal,
                total_llm_calls=1
            )
            return

        fetch_result = await download_recap_pdf(
            pdf_url=resolved_pdf_url,
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
                total_api_calls=api_calls_for_deal,
                total_llm_calls=1
            )
            return

        # Success - document downloaded
        logger.info(f"Successfully downloaded PDF: {deal_id}")
        telemetry.log_pipeline_terminal(
            deal=deal,
            pipeline_status="DOWNLOADED",
            total_api_calls=api_calls_for_deal,
            total_llm_calls=1,
            downloaded_file=fetch_result["local_file_path"]
        )

    except DailyBudgetExhausted:
        logger.error(f"Daily API budget exhausted. Stopping pipeline.")
        telemetry.log_pipeline_terminal(
            deal=deal,
            pipeline_status="NOT_FOUND",  # Treat as not found since we couldn't search
            total_api_calls=api_calls_for_deal,
            total_llm_calls=0
        )
        raise
    except Exception as e:
        logger.error(f"Error processing deal {deal_id}: {str(e)}")
        telemetry.log_pipeline_terminal(
            deal=deal,
            pipeline_status="NOT_FOUND",  # Treat as not found on error
            total_api_calls=api_calls_for_deal,
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
            deals = json.load(f)
        logger.info(f"Loaded {len(deals)} deals from dataset")
    except Exception as e:
        logger.error(f"Failed to load dataset: {str(e)}")
        return

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
    asyncio.run(main())