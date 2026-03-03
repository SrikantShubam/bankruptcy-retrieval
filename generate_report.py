import asyncio
import json
import sys
import os
from dotenv import load_dotenv
load_dotenv('.env')

# Add the shared directory to the path
sys.path.insert(0, '../bankruptcy-retrieval')

from shared.config import is_excluded
from shared.gatekeeper import LLMGatekeeper, CandidateDocument
from shared.telemetry import TelemetryLogger
from scout import find_document_for_deal, DailyBudgetExhausted
from fetcher import download_recap_pdf, close_http_client as close_fetcher_client

# Standard test deals for quick validation
STANDARD_TEST_DEALS = [
    "wework-2023", "rite-aid-2023", "blockfi-2022",
    "bed-bath-beyond-2023", "yellow-corp-2023", "mitchells-butlers-2023",
    "kidoz-2023", "svb-financial-2023", "talen-energy-2023", "medical-decoy-c"
]

DATASET_PATH = "../bankruptcy-retrieval/data/deals_dataset.json"
GROUND_TRUTH_PATH = "../bankruptcy-retrieval/data/ground_truth.json"
WORKTREE_NAME = "A"

async def process_deal_for_report(deal: dict, gatekeeper: LLMGatekeeper, telemetry: TelemetryLogger) -> dict:
    """
    Process a single deal and return a report dictionary
    """
    deal_id = deal.get("deal_id", "unknown")
    company_name = deal.get("company_name", "unknown")

    result = {
        "deal_id": deal_id,
        "candidate_title": "",
        "gatekeeper_score": "",
        "status": "NOT_FOUND"
    }

    # Check if deal should be excluded
    if is_excluded(deal):
        result["status"] = "ALREADY_PROCESSED"
        return result

    try:
        # Single-phase search using V4 API
        candidate_data = await find_document_for_deal(
            company_name=company_name,
            filing_year=deal.get("filing_year", 2023),
            court=deal.get("court", "")
        )

        if not candidate_data:
            result["status"] = "NOT_FOUND"
            return result

        result["candidate_title"] = candidate_data["docket_title"][:60]
        result["status"] = "FOUND"

        # Create candidate document for gatekeeper
        candidate = CandidateDocument(
            deal_id=deal_id,
            source=candidate_data["source"],
            docket_entry_id=candidate_data["docket_entry_id"],
            docket_title=candidate_data["docket_title"],
            filing_date=candidate_data["filing_date"],
            attachment_descriptions=candidate_data["attachment_descriptions"],
            resolved_pdf_url=candidate_data["resolved_pdf_url"],
            api_calls_consumed=candidate_data.get("api_calls_consumed", 0)
        )

        # Gatekeeper evaluation
        try:
            gatekeeper_result = await gatekeeper.evaluate(candidate)
            result["gatekeeper_score"] = f"{gatekeeper_result.score:.2f}"
            if gatekeeper_result.verdict == "DOWNLOAD":
                result["status"] = "APPROVED"
            else:
                result["status"] = "REJECTED"
        except Exception as e:
            result["gatekeeper_score"] = "ERROR"
            result["status"] = "GATEKEEPER_ERROR"

    except DailyBudgetExhausted:
        result["status"] = "BUDGET_EXHAUSTED"
    except Exception as e:
        result["status"] = "ERROR"

    return result

async def main():
    """Generate detailed report for standard test deals"""
    print("Running standard test deals report...")

    # Load dataset
    try:
        with open(DATASET_PATH, 'r') as f:
            all_deals = json.load(f)
    except Exception as e:
        print(f"Failed to load dataset: {str(e)}")
        return

    # Filter standard test deals
    deals = [d for d in all_deals if d["deal_id"] in STANDARD_TEST_DEALS]
    deals.sort(key=lambda d: STANDARD_TEST_DEALS.index(d["deal_id"]) if d["deal_id"] in STANDARD_TEST_DEALS else len(STANDARD_TEST_DEALS))

    # Initialize gatekeeper
    gatekeeper = LLMGatekeeper()

    # Initialize telemetry
    telemetry = TelemetryLogger(
        worktree=WORKTREE_NAME,
        ground_truth_path=GROUND_TRUTH_PATH,
        log_dir="./logs"
    )

    # Process deals and collect results
    results = []
    for deal in deals:
        try:
            result = await process_deal_for_report(deal, gatekeeper, telemetry)
            results.append(result)
            print(f"{result['deal_id']} | {result['candidate_title']:<60} | {result['gatekeeper_score']:<6} | {result['status']}")
        except Exception as e:
            result = {
                "deal_id": deal.get("deal_id", "unknown"),
                "candidate_title": "",
                "gatekeeper_score": "ERROR",
                "status": "PROCESSING_ERROR"
            }
            results.append(result)
            print(f"{result['deal_id']} | {result['candidate_title']:<60} | {result['gatekeeper_score']:<6} | {result['status']}")

    # Calculate metrics (simplified since we don't have ground truth)
    found_count = sum(1 for r in results if r["status"] == "FOUND")
    approved_count = sum(1 for r in results if r["status"] == "APPROVED")
    rejected_count = sum(1 for r in results if r["status"] == "REJECTED")
    not_found_count = sum(1 for r in results if r["status"] == "NOT_FOUND")

    print("\nSummary:")
    print(f"Total deals processed: {len(results)}")
    print(f"Documents found: {found_count}")
    print(f"Gatekeeper approved: {approved_count}")
    print(f"Gatekeeper rejected: {rejected_count}")
    print(f"Not found: {not_found_count}")

    # Close HTTP clients
    await close_fetcher_client()

if __name__ == "__main__":
    asyncio.run(main())