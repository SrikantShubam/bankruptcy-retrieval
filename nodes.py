"""
nodes.py
─────────────────────────────────────────────────────────────────────────────
LangGraph node implementations for Worktree C.

Real implementations of Scout, Gatekeeper, and Fetcher nodes.

Schema reference: WORKTREE_C_MULTI_AGENT.md §4
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import logging
import os
from pathlib import Path

from state_types import PipelineState

logger = logging.getLogger(__name__)

# Import shared modules
from shared.config import (
    EXCLUDED_DEALS,
    EXCLUDED_DEAL_IDS,
    ORCHESTRATOR_MODEL,
    MAX_PDF_BYTES,
    DOWNLOAD_DIR,
    PRIORITY_KEYWORDS,
    MAX_KEYWORD_QUERIES_PER_DEAL,
    get_court_slug,
)
from shared.gatekeeper import LLMGatekeeper, CandidateDocument as GatekeeperCandidate
from tools import (
    search_courtlistener_api,
    search_claims_agent_browser,
    search_courtlistener_fulltext,
)


# ─────────────────────────────────────────────────────────────────────────────
# Exclusion Check Node
# ─────────────────────────────────────────────────────────────────────────────

async def exclusion_check_node(state: PipelineState) -> PipelineState:
    """Check if deal is in excluded set."""
    deal = state.get("deal", {})
    company_name = deal.get("company_name", "")
    already_processed = deal.get("already_processed", False)
    
    is_excluded = (
        company_name in EXCLUDED_DEALS
        or deal.get("deal_id", "") in EXCLUDED_DEAL_IDS
        or already_processed
    )
    
    if is_excluded:
        return {
            **state,
            "pipeline_status": "ALREADY_PROCESSED",
            "final_status": "ALREADY_PROCESSED"
        }
    
    return {**state, "pipeline_status": "active"}


# ─────────────────────────────────────────────────────────────────────────────
# Scout Node - Uses CourtListener API directly
# ─────────────────────────────────────────────────────────────────────────────

async def scout_node(state: PipelineState) -> PipelineState:
    """Scout agent searches for documents using CourtListener API."""
    import httpx
    from shared.config import COURTLISTENER_API_TOKEN, COURTLISTENER_BASE_URL
    
    deal = state.get("deal", {})
    deal_id = deal.get("deal_id", "")
    company_name = deal.get("company_name", "")
    filing_year = deal.get("filing_year", 2023)
    court = deal.get("court")
    
    # Convert court to slug
    court_slug = get_court_slug(court)
    
    headers = {}
    if COURTLISTENER_API_TOKEN:
        headers["Authorization"] = f"Token {COURTLISTENER_API_TOKEN}"
    
    candidates = []
    api_calls_made = 0
    search_attempts = state.get("search_attempts", 0) + 1
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # Phase 1: Search for dockets using the V4 search endpoint
            search_params = {
                "q": company_name,
            }
            
            response = await client.get(
                f"{COURTLISTENER_BASE_URL}/search/",
                params=search_params,
                headers=headers
            )
            api_calls_made += 1
            
            if response.status_code == 200:
                search_data = response.json()
                results = search_data.get("results", [])
                
                if not results:
                    return {
                        **state,
                        "search_attempts": search_attempts,
                        "candidates": [],
                        "api_calls_used": state.get("api_calls_used", 0) + api_calls_made
                    }
                
                # Get first matching result with a docket_id
                docket_id = None
                for result in results:
                    # V4 search results have docket_id directly
                    if result.get("docket_id"):
                        docket_id = result.get("docket_id")
                        break
                
                if not docket_id:
                    return {
                        **state,
                        "search_attempts": search_attempts,
                        "candidates": [],
                        "api_calls_used": state.get("api_calls_used", 0) + api_calls_made
                    }
                
                # Phase 2: Search docket entries with priority keywords
                for keyword in PRIORITY_KEYWORDS[:MAX_KEYWORD_QUERIES_PER_DEAL]:
                    entries_response = await client.get(
                        f"{COURTLISTENER_BASE_URL}/docket-entries/",
                        params={
                            "docket": docket_id,
                            "description__icontains": keyword,
                            "format": "json",
                            "limit": 10,
                            "order_by": "-date_filed",
                        },
                        headers=headers
                    )
                    api_calls_made += 1
                    
                    if entries_response.status_code == 200:
                        entries_data = entries_response.json()
                        for entry in entries_data.get("results", []):
                            description = entry.get("description", "")
                            if not description:
                                continue
                            
                            # Get PDF URL from recap documents
                            pdf_url = None
                            recap_docs = entry.get("recap_documents", [])
                            for doc in recap_docs:
                                if doc.get("pdf_url"):
                                    pdf_url = doc.get("pdf_url")
                                    break
                            
                            if not pdf_url:
                                continue
                            
                            candidate = {
                                "deal_id": deal_id,
                                "source": "courtlistener",
                                "docket_entry_id": str(entry.get("id", "")),
                                "docket_title": description,
                                "filing_date": entry.get("date_filed", "")[:10] if entry.get("date_filed") else "",
                                "attachment_descriptions": [],
                                "resolved_pdf_url": pdf_url,
                                "api_calls_consumed": api_calls_made,
                            }
                            candidates.append(candidate)
                            break  # Found one, stop searching
                        
                        if candidates:
                            break  # Found candidate, stop keywords
                
    except Exception as e:
        logger.warning(f"Scout error for {deal_id}: {e}")
    
    return {
        **state,
        "search_attempts": search_attempts,
        "candidates": candidates,
        "api_calls_used": state.get("api_calls_used", 0) + api_calls_made
    }


# ─────────────────────────────────────────────────────────────────────────────
# Gatekeeper Node - Evaluates candidates
# ─────────────────────────────────────────────────────────────────────────────

async def gatekeeper_node(state: PipelineState) -> PipelineState:
    """Gatekeeper evaluates candidates for download decision."""
    candidates = state.get("candidates", [])
    
    # Short-circuit if already have DOWNLOAD verdict
    existing_results = state.get("gatekeeper_results", [])
    for result in existing_results:
        if result.get("verdict") == "DOWNLOAD":
            return state
    
    if not candidates:
        return {
            **state,
            "gatekeeper_results": []
        }
    
    # Use first candidate
    candidate = candidates[0]
    
    # Call gatekeeper
    try:
        gatekeeper = LLMGatekeeper()
        
        gatekeeper_candidate = GatekeeperCandidate(
            deal_id=candidate.get("deal_id", ""),
            source=candidate.get("source", ""),
            docket_entry_id=candidate.get("docket_entry_id", ""),
            docket_title=candidate.get("docket_title", ""),
            filing_date=candidate.get("filing_date", ""),
            attachment_descriptions=candidate.get("attachment_descriptions", []),
            resolved_pdf_url=candidate.get("resolved_pdf_url"),
        )
        
        result = await gatekeeper.evaluate(gatekeeper_candidate)
        
        gatekeeper_result = {
            "verdict": result.verdict,
            "score": result.score,
            "reasoning": result.reasoning,
            "token_count": result.token_count,
            "model_used": result.model_used,
            "docket_title": candidate.get("docket_title", ""),
            "attachment_descriptions": candidate.get("attachment_descriptions", []),
        }
        
    except Exception as e:
        logger.warning(f"Gatekeeper error: {e}")
        gatekeeper_result = {
            "verdict": "SKIP",
            "score": 0.0,
            "reasoning": f"Gatekeeper error: {str(e)[:100]}",
            "token_count": 0,
            "model_used": "",
        }
    
    return {
        **state,
        "gatekeeper_results": existing_results + [gatekeeper_result]
    }


# ─────────────────────────────────────────────────────────────────────────────
# Fetcher Node - Downloads PDFs
# ─────────────────────────────────────────────────────────────────────────────

async def fetcher_node(state: PipelineState) -> PipelineState:
    """Fetcher downloads approved documents."""
    candidates = state.get("candidates", [])
    gatekeeper_results = state.get("gatekeeper_results", [])
    
    if not candidates or not gatekeeper_results:
        return {**state, "downloaded_files": []}
    
    # Check if any result says DOWNLOAD
    has_download = False
    for result in gatekeeper_results:
        if result.get("verdict") == "DOWNLOAD":
            has_download = True
            break
    
    if not has_download:
        return {**state, "downloaded_files": []}
    
    # Use first candidate with DOWNLOAD verdict
    candidate = candidates[0]
    pdf_url = candidate.get("resolved_pdf_url")
    
    if not pdf_url:
        return {**state, "downloaded_files": []}
    
    deal = state.get("deal", {})
    deal_id = deal.get("deal_id", "unknown")
    
    # Create download directory
    download_path = Path(DOWNLOAD_DIR) / deal_id
    download_path.mkdir(parents=True, exist_ok=True)
    
    # Determine filename
    filename = f"{candidate.get('docket_entry_id', 'doc')}.pdf"
    file_path = download_path / filename
    
    downloaded_files = []
    
    try:
        import httpx
        
        async with httpx.AsyncClient(timeout=60.0, follow_redirects=True) as client:
            response = await client.get(pdf_url)
            
            if response.status_code == 200:
                content_length = response.headers.get("content-length")
                if content_length and int(content_length) > MAX_PDF_BYTES:
                    logger.warning(f"PDF too large for {deal_id}: {content_length} bytes")
                    return {**state, "downloaded_files": []}
                
                # Save file
                with open(file_path, "wb") as f:
                    async for chunk in response.aiter_bytes(chunk_size=8192):
                        f.write(chunk)
                
                downloaded_files = [str(file_path)]
                logger.info(f"Downloaded {deal_id} to {file_path}")
            else:
                logger.warning(f"Download failed for {deal_id}: HTTP {response.status_code}")
    
    except Exception as e:
        logger.warning(f"Fetch error for {deal_id}: {e}")
    
    return {
        **state,
        "downloaded_files": downloaded_files
    }


# ─────────────────────────────────────────────────────────────────────────────
# Fallback Node
# ─────────────────────────────────────────────────────────────────────────────

async def fallback_node(state: PipelineState) -> PipelineState:
    """Fallback handler for failed downloads."""
    return {
        **state,
        "pipeline_status": "FETCH_FAILED"
    }


# ─────────────────────────────────────────────────────────────────────────────
# Log Node
# ─────────────────────────────────────────────────────────────────────────────

async def log_node(state: PipelineState) -> PipelineState:
    """Logs terminal state for already_processed or skipped deals."""
    return {
        **state,
        "final_status": state.get("pipeline_status", "UNKNOWN")
    }


# ─────────────────────────────────────────────────────────────────────────────
# Telemetry Node
# ─────────────────────────────────────────────────────────────────────────────

async def telemetry_node(state: PipelineState) -> PipelineState:
    """Logs final telemetry and sets final status."""
    downloaded = state.get("downloaded_files", [])
    if downloaded:
        final_status = "DOWNLOADED"
    else:
        final_status = state.get("pipeline_status", "UNKNOWN")
    
    return {
        **state,
        "final_status": final_status
    }


# ─────────────────────────────────────────────────────────────────────────────
# Export for use in graph.py
# ─────────────────────────────────────────────────────────────────────────────

__all__ = [
    "exclusion_check_node",
    "scout_node",
    "gatekeeper_node",
    "fetcher_node",
    "fallback_node",
    "log_node",
    "telemetry_node",
]
