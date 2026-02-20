"""
main.py
─────────────────────────────────────────────────────────────────────────────
Worktree C - Autonomous Agentic Pipeline Entry Point

This is the main entry point for the LangGraph multi-agent pipeline.
It loads the dataset, runs the graph for each deal, and logs telemetry.

Schema reference: WORKTREE_C_MULTI_AGENT.md
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import asyncio
import json
import logging
import sys
from pathlib import Path

# Add current directory to path for shared imports (same directory structure)
sys.path.insert(0, str(Path(__file__).parent))

from graph import build_graph, PipelineState
from shared.telemetry import TelemetryLogger
from shared.config import is_excluded

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data paths
# ─────────────────────────────────────────────────────────────────────────────

DATA_DIR = Path(__file__).parent / "data"
DEALS_DATASET_PATH = DATA_DIR / "deals_dataset.json"
GROUND_TRUTH_PATH = DATA_DIR / "ground_truth.json"
LOG_DIR = Path(__file__).parent / "logs"


# ─────────────────────────────────────────────────────────────────────────────
# Main async pipeline
# ─────────────────────────────────────────────────────────────────────────────

async def run_pipeline():
    """
    Main async pipeline that processes all deals.
    """
    logger.info("=" * 60)
    logger.info("Worktree C - Autonomous Agentic Pipeline")
    logger.info("=" * 60)
    
    # Load deals dataset
    if not DEALS_DATASET_PATH.exists():
        logger.error(f"Deals dataset not found: {DEALS_DATASET_PATH}")
        return
    
    with open(DEALS_DATASET_PATH) as f:
        deals = json.load(f)
    
    logger.info(f"Loaded {len(deals)} deals from dataset")
    
    # Initialize telemetry logger
    LOG_DIR.mkdir(parents=True, exist_ok=True)
    telemetry = TelemetryLogger(
        worktree="C",
        ground_truth_path=str(GROUND_TRUTH_PATH),
        log_dir=str(LOG_DIR),
    )
    
    # Build the LangGraph
    graph = build_graph()
    logger.info("LangGraph compiled successfully")
    
    # Process each deal
    processed = 0
    skipped = 0
    
    for deal in deals:
        deal_id = deal.get("deal_id", "unknown")
        company_name = deal.get("company_name", "unknown")
        
        logger.info(f"\n{'='*40}")
        logger.info(f"Processing: {deal_id} - {company_name}")
        logger.info(f"{'='*40}")
        
        # Check exclusion BEFORE any processing
        if is_excluded(deal):
            logger.info(f"EXCLUDED: {company_name} (already_processed)")
            telemetry.log_exclusion_skip(deal)
            telemetry.log_pipeline_terminal(
                deal=deal,
                pipeline_status="ALREADY_PROCESSED",
                total_api_calls=0,
                total_llm_calls=0,
            )
            skipped += 1
            continue
        
        # Initialize pipeline state
        initial_state: PipelineState = {
            "deal": deal,
            "search_attempts": 0,
            "candidates": [],
            "gatekeeper_results": [],
            "downloaded_files": [],
            "pipeline_status": "pending",
            "api_calls_used": 0,
            "orchestrator_tokens_used": 0,
            "error_log": [],
            "final_status": "",
        }
        
        # Start deal timer
        telemetry.start_deal(deal_id)
        
        try:
            # Run the graph
            final_state = await graph.ainvoke(initial_state)
            
            # Log terminal status
            final_status = final_state.get("final_status", "UNKNOWN")
            api_calls = final_state.get("api_calls_used", 0)
            
            logger.info(f"Deal {deal_id} completed with status: {final_status}")
            logger.info(f"API calls used: {api_calls}")
            
            # Log pipeline terminal event
            downloaded = final_state.get("downloaded_files", [])
            downloaded_file = downloaded[0] if downloaded else None
            
            telemetry.log_pipeline_terminal(
                deal=deal,
                pipeline_status=final_status,
                total_api_calls=api_calls,
                total_llm_calls=len(final_state.get("gatekeeper_results", [])),
                downloaded_file=downloaded_file,
            )
            
            processed += 1
            
        except Exception as e:
            logger.error(f"Error processing deal {deal_id}: {e}", exc_info=True)
            telemetry.log_pipeline_terminal(
                deal=deal,
                pipeline_status="FETCH_FAILED",
                total_api_calls=initial_state.get("api_calls_used", 0),
                total_llm_calls=0,
            )
    
    # Finalize and compute metrics
    logger.info("\n" + "=" * 60)
    logger.info("Pipeline Complete - Computing Metrics")
    logger.info("=" * 60)
    
    report = telemetry.finalise()
    telemetry.print_summary()
    
    logger.info(f"\nTotal processed: {processed}")
    logger.info(f"Total skipped (excluded): {skipped}")
    logger.info(f"Total deals: {len(deals)}")
    
    return report


# ─────────────────────────────────────────────────────────────────────────────
# Entry point
# ─────────────────────────────────────────────────────────────────────────────

def main():
    """Synchronous entry point."""
    try:
        report = asyncio.run(run_pipeline())
        logger.info("Pipeline completed successfully")
        return 0
    except Exception as e:
        logger.error(f"Pipeline failed: {e}", exc_info=True)
        return 1


if __name__ == "__main__":
    sys.exit(main())
