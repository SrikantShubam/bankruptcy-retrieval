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
    COURTLISTENER_SEARCH_URL,  # V3 search URL (V4 doesn't support `q` param)
)
from shared.gatekeeper import LLMGatekeeper, CandidateDocument as GatekeeperCandidate
from tools import (
    search_courtlistener_api,
    search_claims_agent_browser,
    search_courtlistener_fulltext,
)

# Free-text phrase queries for bankruptcy-related documents
QUERY_TEMPLATES = [
    '"{company}" "first day"',
    '"{company}" "declaration in support"',
    '"{company}" "DIP motion"',
    '"{company}" "debtor in possession"',
    '"{company}" "cash collateral"',
]

DOC_KEYWORDS = [
    "first day declaration",
    "declaration in support of first day",
    "declaration in support of chapter 11 petition",
    "declaration in support of the debtors",
    "in support of first day motions",
    "chapter 11 petitions and first day motions",
    "chapter 11 petition and first day pleadings",
    "first day pleadings",
    "dip motion",
    "debtor in possession financing motion",
    "cash collateral motion",
]

HARD_REJECT = [
    "motion for relief from stay",
    "relief from stay",
    "certificate of service",
    "notice of filing",
    "monthly operating report",
    "fee application",
    "retention application",
    "order regarding",
    "order granting",
    "order approving",
    "pro hac vice",
    "official committee",
    "unsecured creditors",
    "objection",
    "response",
    "statement in respect of",
]


def _description_signal_score(description_lower: str) -> int:
    """Heuristic ranking so scout prefers true first-day declarations."""
    score = 0
    if "first day declaration" in description_lower:
        score += 8
    if "declaration in support of first day" in description_lower:
        score += 7
    if "chapter 11 petitions and first day" in description_lower:
        score += 6
    if "in support of first day motions" in description_lower:
        score += 6
    if "chapter 11 petitions and first day motions" in description_lower:
        score += 6
    if "chapter 11 petition and first day pleadings" in description_lower:
        score += 6
    if "first day pleadings" in description_lower:
        score += 4
    if "declaration in support of chapter 11 petition" in description_lower:
        score += 5
    if "declaration in support of the debtors" in description_lower:
        score += 4
    if "dip motion" in description_lower:
        score += 3
    if "debtor in possession financing motion" in description_lower:
        score += 3
    if "cash collateral motion" in description_lower:
        score += 2
    return score


_COMPANY_STOPWORDS = {
    "inc", "inc.", "llc", "l.l.c.", "corp", "corporation", "company", "co", "co.",
    "holdings", "group", "financial", "finance", "systems", "brands", "the", "and",
}


def _company_tokens(company_name: str) -> list[str]:
    import re
    tokens = [t for t in re.findall(r"[a-z0-9]+", (company_name or "").lower()) if len(t) >= 3]
    return [t for t in tokens if t not in _COMPANY_STOPWORDS]


def _company_matches_deal(company_name: str, case_name: str, description: str) -> bool:
    haystack = f"{case_name or ''} {description or ''}".lower()
    tokens = _company_tokens(company_name)
    if not tokens:
        return True
    # Require at least one meaningful company token in case/title metadata.
    return any(tok in haystack for tok in tokens)


def _court_matches_deal(deal_court: str, result_court: str) -> bool:
    if not deal_court:
        return True
    slug = get_court_slug(deal_court)
    court_text = (result_court or "").lower()
    slug_markers = {
        "njd": ["new jersey"],
        "nysd": ["s.d. new york", "southern district of new york"],
        "deb": ["delaware"],
        "txsd": ["s.d. texas", "southern district of texas"],
        "flmd": ["m.d. florida", "middle district of florida"],
    }
    markers = slug_markers.get(slug)
    if not markers:
        return True
    return any(m in court_text for m in markers)


def _fallback_gatekeeper_from_title(title: str) -> dict:
    """Deterministic backup when LLM gatekeeper is unavailable."""
    t = (title or "").lower()
    has_signal = any(kw in t for kw in DOC_KEYWORDS)
    is_noise = any(rj in t for rj in HARD_REJECT)
    if has_signal and not is_noise:
        return {
            "verdict": "DOWNLOAD",
            "score": 0.91,
            "reasoning": "Metadata-only fallback matched first-day financing signals.",
            "token_count": 0,
            "model_used": "heuristic_fallback",
        }
    return {
        "verdict": "SKIP",
        "score": 0.05,
        "reasoning": "Metadata-only fallback found no reliable first-day signal.",
        "token_count": 0,
        "model_used": "heuristic_fallback",
    }


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
    
    return {**state, "pipeline_status": "active", "final_status": "active"}


# ─────────────────────────────────────────────────────────────────────────────
# Scout Node - Uses CourtListener V4 Search API
# ─────────────────────────────────────────────────────────────────────────────

# V4 search endpoint - supports `q` parameter with full-text search
COURTLISTENER_V4_SEARCH = "https://www.courtlistener.com/api/rest/v4/search/"

async def scout_node(state: PipelineState) -> PipelineState:
    """
    Scout agent searches for documents using CourtListener V4 Search API.
    Falls back to claims agent browser tool if no results.
    """
    import httpx
    import json
    from shared.config import (
        COURTLISTENER_API_TOKEN,
    )

    deal = state.get("deal", {})
    deal_id = deal.get("deal_id", "")
    company_name = deal.get("company_name", "")
    filing_year = deal.get("filing_year", 2023)
    deal_court = deal.get("court", "")
    claims_agent = deal.get("claims_agent")

    headers = {"Authorization": f"Token {COURTLISTENER_API_TOKEN}"} if COURTLISTENER_API_TOKEN else {}
    candidates = []
    api_calls_made = 0
    search_attempts = state.get("search_attempts", 0) + 1

    # ── Phase 1: CourtListener V4 search with field-targeted queries ──
    async with httpx.AsyncClient(timeout=30.0) as client:
        for query_template in QUERY_TEMPLATES[:MAX_KEYWORD_QUERIES_PER_DEAL]:
            params = {
                "q": query_template.format(company=company_name),
                "type": "r",  # RECAP documents
                "available_only": "on",
                "order_by": "score desc",
                "filed_after": f"{filing_year}-01-01",
                "filed_before": f"{filing_year}-12-31",
            }

            response = await client.get(
                COURTLISTENER_V4_SEARCH,
                params=params,
                headers=headers
            )
            api_calls_made += 1

            if response.status_code == 200:
                search_data = response.json()
                results = search_data.get("results", [])

                if results:
                    # type=r returns docket-level rows with nested recap_documents.
                    best_candidate = None
                    best_score = -1
                    for result in results:
                        date_filed = (result.get("dateFiled") or "")[:10]
                        case_name = result.get("caseName", "")
                        result_court = result.get("court", "")
                        for doc in result.get("recap_documents", []):
                            filepath = doc.get("filepath_local", "")
                            if not filepath or not doc.get("is_available", False):
                                continue

                            description = doc.get("description", "")
                            if not _company_matches_deal(company_name, case_name, description):
                                continue
                            if not _court_matches_deal(deal_court, result_court):
                                continue
                            description_lower = description.lower()
                            has_signal = any(kw in description_lower for kw in DOC_KEYWORDS)
                            is_noise = any(rj in description_lower for rj in HARD_REJECT)
                            if not has_signal or is_noise:
                                continue
                            score = _description_signal_score(description_lower)
                            candidate = {
                                "deal_id": deal_id,
                                "source": "courtlistener",
                                "docket_entry_id": str(doc.get("docket_entry_id", doc.get("id", ""))),
                                "docket_title": description[:200],
                                "filing_date": doc.get("entry_date_filed") or date_filed,
                                "attachment_descriptions": [],
                                "resolved_pdf_url": f"https://storage.courtlistener.com/{filepath}",
                                "api_calls_consumed": api_calls_made,
                            }
                            if score > best_score:
                                best_score = score
                                best_candidate = candidate

                    if best_candidate:
                        candidates.append(best_candidate)

                    if candidates:
                        break  # Found candidate, stop phrase queries
    
    # ── Phase 2: Claims agent browser tool fallback ──
    if not candidates and claims_agent:
        try:
            from tools import search_claims_agent_browser
            result_json = await search_claims_agent_browser.ainvoke({
                "company_name": company_name,
                "claims_agent": claims_agent
            })
            browser_candidates = json.loads(result_json) if result_json else []
            candidates.extend(browser_candidates)
            logger.info(f"Browser fallback for {deal_id}: found {len(browser_candidates)} candidates")
        except Exception as e:
            logger.warning(f"Browser tool failed for {deal_id}: {e}")
    
    # Debug: Log final API calls state
    final_api_calls = state.get("api_calls_used", 0) + api_calls_made
    logger.debug(f"[SCOUT] Final API calls after scout_node: {final_api_calls}")
    logger.debug(f"[SCOUT] API calls made in this node: {api_calls_made}")

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
    
    # Log the docket_title being evaluated (DEBUG: why so many SKIPs?)
    logger.info(f"[GATEKEEPER] Evaluating deal_id={candidate.get('deal_id')} | docket_title='{candidate.get('docket_title')}'")
    
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
        
        # Log gatekeeper result (DEBUG: track scores for borderline cases)
        logger.info(f"[GATEKEEPER] Result for {candidate.get('deal_id')}: verdict={result.verdict} score={result.score} reasoning={result.reasoning[:100] if result.reasoning else 'N/A'}...")
        
        gatekeeper_result = {
            "verdict": result.verdict,
            "score": result.score,
            "reasoning": result.reasoning,
            "token_count": result.token_count,
            "model_used": result.model_used,
            "docket_title": candidate.get("docket_title", ""),
            "attachment_descriptions": candidate.get("attachment_descriptions", []),
        }
        llm_failed = (result.error is not None) or (result.reasoning or "").lower().startswith("llm call failed")
        if llm_failed:
            gatekeeper_result = {
                **_fallback_gatekeeper_from_title(candidate.get("docket_title", "")),
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
        "pipeline_status": "FETCH_FAILED",
        "final_status": "FETCH_FAILED"
    }


# ─────────────────────────────────────────────────────────────────────────────
# Log Node
# ─────────────────────────────────────────────────────────────────────────────

async def log_node(state: PipelineState) -> PipelineState:
    """Logs terminal state for already_processed or skipped deals."""
    # Determine final status based on what happened
    candidates = state.get("candidates", [])
    gatekeeper_results = state.get("gatekeeper_results", [])
    downloaded = state.get("downloaded_files", [])
    pipeline_status = state.get("pipeline_status", "UNKNOWN")
    
    # If we have downloaded files, status is DOWNLOADED
    if downloaded:
        final_status = "DOWNLOADED"
        pipeline_status = "DOWNLOADED"
    # If no candidates found at all, it's NOT_FOUND
    elif not candidates:
        final_status = "NOT_FOUND"
        pipeline_status = "NOT_FOUND"
    # If gatekeeper returned SKIP verdict, it's SKIPPED
    elif any(r.get("verdict") == "SKIP" for r in gatekeeper_results):
        final_status = "SKIPPED"
        pipeline_status = "SKIPPED"
    # Otherwise use the pipeline_status
    else:
        final_status = pipeline_status
    
    return {
        **state,
        "pipeline_status": pipeline_status,
        "final_status": final_status
    }


# ─────────────────────────────────────────────────────────────────────────────
# Telemetry Node
# ─────────────────────────────────────────────────────────────────────────────

async def telemetry_node(state: PipelineState) -> PipelineState:
    """Logs final telemetry and sets final status."""
    downloaded = state.get("downloaded_files", [])
    if downloaded:
        final_status = "DOWNLOADED"
        pipeline_status = "DOWNLOADED"
    else:
        final_status = state.get("pipeline_status", "UNKNOWN")
        pipeline_status = final_status
    
    return {
        **state,
        "pipeline_status": pipeline_status,
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
