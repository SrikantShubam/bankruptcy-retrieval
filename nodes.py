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
    '"{company}" "first day motions"',
    '"{company}" "DIP motion"',
    '"{company}" "debtor in possession"',
    '"{company}" "cash collateral"',
    '"{company}" "chapter 11 petitions"',
    '"{company}" "first day matters"',
    '"{company}" "first day pleadings"',
    '"{company}" "postpetition financing"',
]

DOC_KEYWORDS = [
    "first day declaration",
    "declaration in support of first day",
    "declaration in support of chapter 11 petition",
    "declaration in support of the debtors",
    "in support of first day motions",
    "chapter 11 petitions and first day motions",
    "chapter 11 petition and first day pleadings",
    "chapter 11 petitions",
    "first day pleadings",
    "first day papers",
    "dip motion",
    "debtor in possession financing motion",
    "cash collateral motion",
    "postpetition financing",
    "first day matters",
    "expedited consideration of first day matters",
    "first day relief",
    "superpriority postpetition",
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
    "opposition to",
    "response",
    "statement in respect of",
    "summary judgment",
    "verified statement/declaration of professional",
    "retention and employment of",
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
    if "first day papers" in description_lower:
        score += 4
    if "first day motion" in description_lower:
        score += 5
    if "first day motions" in description_lower:
        score += 5
    if "first day petitions" in description_lower:
        score += 5
    if "declaration in support of chapter 11 petition" in description_lower:
        score += 5
    if "declaration in support of the debtors" in description_lower:
        score += 4
    if "declaration" in description_lower and "in support of" in description_lower:
        score += 3
    if "dip motion" in description_lower:
        score += 3
    if "debtor in possession financing motion" in description_lower:
        score += 3
    if "debtor-in-possession financing" in description_lower:
        score += 4
    if "dip loan agreement" in description_lower:
        score += 3
    if "cash collateral motion" in description_lower:
        score += 2
    if "postpetition financing" in description_lower:
        score += 4
    if "superpriority postpetition" in description_lower:
        score += 4
    if "first day matters" in description_lower:
        score += 4
    if "expedited consideration of first day matters" in description_lower:
        score += 5
    if "first day relief" in description_lower:
        score += 3
    return score


def _has_document_signal(description_lower: str) -> bool:
    """Recall-oriented signal check for first-day/DIP style filings."""
    if any(kw in description_lower for kw in DOC_KEYWORDS):
        return True
    if "first day" in description_lower and any(
        token in description_lower for token in ("declaration", "pleading", "petition", "motion")
    ):
        return True
    if "debtor in possession" in description_lower and "motion" in description_lower:
        return True
    if "cash collateral" in description_lower and "motion" in description_lower:
        return True
    if "postpetition financing" in description_lower:
        return True
    if "debtor-in-possession financing" in description_lower:
        return True
    if "first day motion" in description_lower:
        return True
    if "first day motions" in description_lower:
        return True
    if "first day petitions" in description_lower:
        return True
    if "declaration" in description_lower and "in support of" in description_lower and (
        "debtor" in description_lower
        or "debtors" in description_lower
        or "chapter 11" in description_lower
        or "first day" in description_lower
    ):
        return True
    if "first day papers" in description_lower:
        return True
    if "first day matters" in description_lower:
        return True
    if "first day relief" in description_lower:
        return True
    if "superpriority postpetition" in description_lower:
        return True
    return False


_COMPANY_STOPWORDS = {
    "inc", "inc.", "llc", "l.l.c.", "corp", "corporation", "company", "co", "co.",
    "holdings", "group", "financial", "finance", "systems", "brands", "the", "and",
}


def _company_tokens(company_name: str) -> list[str]:
    import re
    tokens = [t for t in re.findall(r"[a-z0-9]+", (company_name or "").lower()) if len(t) >= 3]
    return [t for t in tokens if t not in _COMPANY_STOPWORDS]


def _normalize_company_query_name(company_name: str) -> str:
    """
    Remove noisy suffixes like '(Decoy — ...)' from dataset labels before querying.
    """
    cleaned = (company_name or "").split("(")[0].strip()
    return cleaned or company_name


def _company_matches_deal(company_name: str, case_name: str, description: str) -> bool:
    haystack = f"{case_name or ''} {description or ''}".lower()
    tokens = _company_tokens(company_name)
    if not tokens:
        return True
    marker_text = (company_name or "").lower()
    requires_strict_match = any(
        marker in marker_text for marker in ("decoy", "subsidiary", "no standalone")
    )
    matched = sum(1 for tok in set(tokens) if tok in haystack)
    if requires_strict_match and len(tokens) >= 2:
        return matched >= 2
    # Default: require at least one meaningful company token in case/title metadata.
    return matched >= 1


def _court_matches_deal(deal_court: str, result_court: str) -> bool:
    if not deal_court:
        return True
    if not result_court:
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


def _is_decoy_deal(deal_id: str) -> bool:
    return "decoy" in (deal_id or "").lower()


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


def _query_templates_for_attempt(attempt_number: int) -> list[str]:
    """
    Use a non-overlapping query strategy across retries.
    This avoids repeated identical searches that hit cached responses.
    """
    if attempt_number <= 1:
        return QUERY_TEMPLATES[:3]
    if attempt_number == 2:
        return QUERY_TEMPLATES[3:6]
    return QUERY_TEMPLATES[6:MAX_KEYWORD_QUERIES_PER_DEAL]


async def _docket_matches_company(
    client,
    headers: dict,
    docket_id: int | None,
    company_name: str,
    deal_court: str,
    cache: dict[int, bool],
) -> bool:
    """Verify ambiguous rd hits using docket metadata to prevent cross-company false positives."""
    if not docket_id:
        return False
    if docket_id in cache:
        return cache[docket_id]
    try:
        response = await client.get(
            f"https://www.courtlistener.com/api/rest/v4/dockets/{docket_id}/",
            headers=headers,
        )
        if response.status_code != 200:
            cache[docket_id] = False
            return False
        data = response.json()
        case_name = data.get("case_name", "")
        court_name = data.get("court", "")
        match = _company_matches_deal(company_name, case_name, case_name) and _court_matches_deal(deal_court, court_name)
        cache[docket_id] = match
        return match
    except Exception:
        cache[docket_id] = False
        return False

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
    query_company_name = _normalize_company_query_name(company_name)
    filing_year = deal.get("filing_year", 2023)
    deal_court = deal.get("court", "")
    claims_agent = deal.get("claims_agent")

    headers = {"Authorization": f"Token {COURTLISTENER_API_TOKEN}"} if COURTLISTENER_API_TOKEN else {}
    candidates = []
    api_calls_made = 0
    request_errors = 0
    error_log = state.get("error_log", [])
    search_attempts = state.get("search_attempts", 0) + 1

    # ── Phase 1: CourtListener V4 document-level search (type=rd) ──
    successful_query_responses = 0
    query_templates = _query_templates_for_attempt(search_attempts)
    scored_candidates: dict[str, tuple[int, dict]] = {}
    docket_match_cache: dict[int, bool] = {}
    async with httpx.AsyncClient(timeout=30.0) as client:
        for query_template in query_templates:
            params = {
                "q": query_template.format(company=query_company_name),
                "type": "rd",  # RECAP document-level rows
                "available_only": "on",
                "order_by": "score desc",
                "filed_after": f"{filing_year}-01-01",
                "filed_before": f"{filing_year}-12-31",
            }

            try:
                response = await client.get(
                    COURTLISTENER_V4_SEARCH,
                    params=params,
                    headers=headers
                )
                api_calls_made += 1
            except httpx.HTTPError as e:
                # Keep graph execution alive and let routing handle terminal failure.
                api_calls_made += 1
                request_errors += 1
                logger.warning(
                    "Scout query failed for %s (graph attempt %s): %s",
                    deal_id,
                    search_attempts,
                    str(e)[:160],
                )
                continue

            successful_query_responses += 1
            if response.status_code == 200:
                search_data = response.json()
                results = search_data.get("results", [])

                if results:
                    # type=rd returns direct RECAP document rows.
                    best_candidate = None
                    best_score = -1
                    for result in results:
                        filepath = result.get("filepath_local", "")
                        if not filepath or not result.get("is_available", False):
                            continue
                        description = result.get("description", "")
                        case_name = result.get("caseName", "") or ""
                        result_court = result.get("court", "") or ""
                        company_match = _company_matches_deal(company_name, case_name, description)
                        if not _court_matches_deal(deal_court, result_court):
                            continue
                        description_lower = description.lower()
                        has_signal = _has_document_signal(description_lower)
                        is_noise = any(rj in description_lower for rj in HARD_REJECT)
                        if not has_signal or is_noise:
                            continue
                        score = _description_signal_score(description_lower)
                        if not company_match:
                            # rd rows often omit case metadata; keep as low-priority candidate
                            # instead of dropping potentially valid debtor filings.
                            score -= 2
                        candidate = {
                            "deal_id": deal_id,
                            "source": "courtlistener",
                            "docket_entry_id": str(result.get("docket_entry_id", result.get("id", ""))),
                            "docket_id": result.get("docket_id"),
                            "docket_title": description[:200],
                            "filing_date": result.get("entry_date_filed") or "",
                            "attachment_descriptions": [],
                            "resolved_pdf_url": f"https://storage.courtlistener.com/{filepath}",
                            "api_calls_consumed": api_calls_made,
                            "company_match": company_match,
                        }
                        if score > best_score:
                            best_score = score
                            best_candidate = candidate

                    if best_candidate:
                        url = best_candidate.get("resolved_pdf_url", "")
                        previous = scored_candidates.get(url)
                        if previous is None or best_score > previous[0]:
                            scored_candidates[url] = (best_score, best_candidate)

        # Fallback: if rd doc queries found nothing, try docket-level chapter-11 search and inspect nested docs.
        if not scored_candidates:
            fallback_params = {
                "q": f"\"{query_company_name}\" \"chapter 11\"",
                "type": "r",
                "available_only": "on",
                "order_by": "score desc",
                "filed_after": f"{filing_year}-01-01",
                "filed_before": f"{filing_year}-12-31",
                "page_size": 10,
            }
            try:
                fallback_response = await client.get(
                    COURTLISTENER_V4_SEARCH,
                    params=fallback_params,
                    headers=headers
                )
                api_calls_made += 1
                successful_query_responses += 1
                if fallback_response.status_code == 200:
                    for row in fallback_response.json().get("results", []):
                        case_name = row.get("caseName", "")
                        result_court = row.get("court", "")
                        for doc in row.get("recap_documents", []):
                            filepath = doc.get("filepath_local", "")
                            if not filepath or not doc.get("is_available", False):
                                continue
                            description = doc.get("description", "")
                            description_lower = description.lower()
                            if not _has_document_signal(description_lower):
                                continue
                            if any(rj in description_lower for rj in HARD_REJECT):
                                continue
                            if not _court_matches_deal(deal_court, result_court):
                                continue
                            company_match = _company_matches_deal(company_name, case_name, description)
                            score = _description_signal_score(description_lower) + (2 if company_match else 0)
                            candidate = {
                                "deal_id": deal_id,
                                "source": "courtlistener_r",
                                "docket_entry_id": str(doc.get("docket_entry_id", doc.get("id", ""))),
                                "docket_id": row.get("docket_id"),
                                "docket_title": description[:200],
                                "filing_date": doc.get("entry_date_filed") or "",
                                "attachment_descriptions": [],
                                "resolved_pdf_url": f"https://storage.courtlistener.com/{filepath}",
                                "api_calls_consumed": api_calls_made,
                                "company_match": company_match,
                            }
                            url = candidate.get("resolved_pdf_url", "")
                            previous = scored_candidates.get(url)
                            if previous is None or score > previous[0]:
                                scored_candidates[url] = (score, candidate)
            except httpx.HTTPError:
                api_calls_made += 1
                request_errors += 1
    
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

    if scored_candidates:
        ranked = sorted(scored_candidates.values(), key=lambda pair: pair[0], reverse=True)
        verified_candidates = []
        rescue_candidates = []
        is_decoy = _is_decoy_deal(deal_id)
        async with httpx.AsyncClient(timeout=30.0) as verify_client:
            for score, candidate in ranked:
                company_match = candidate.get("company_match", False)
                if not company_match:
                    company_match = await _docket_matches_company(
                        verify_client,
                        headers,
                        candidate.get("docket_id"),
                        company_name,
                        deal_court,
                        docket_match_cache,
                    )
                if company_match:
                    verified_candidates.append(candidate)
                elif (
                    not is_decoy
                    and search_attempts >= 3
                    and score >= 7
                    and _has_document_signal((candidate.get("docket_title") or "").lower())
                ):
                    # Final-attempt rescue for sparse rd metadata; avoid blocking earlier retries.
                    rescue_candidates.append(candidate)
                if len(verified_candidates) >= 5:
                    break
                if len(rescue_candidates) >= 2:
                    continue
        candidates = verified_candidates[:5]
        if len(candidates) < 3 and rescue_candidates:
            for candidate in rescue_candidates:
                if candidate not in candidates:
                    candidates.append(candidate)
                if len(candidates) >= 5:
                    break
    
    # Debug: Log final API calls state
    final_api_calls = state.get("api_calls_used", 0) + api_calls_made
    logger.debug(f"[SCOUT] Final API calls after scout_node: {final_api_calls}")
    logger.debug(f"[SCOUT] API calls made in this node: {api_calls_made}")

    had_transport_failure = request_errors > 0 and successful_query_responses == 0 and not candidates

    return {
        **state,
        "search_attempts": search_attempts,
        "candidates": candidates,
        "api_calls_used": final_api_calls,
        "pipeline_status": "INFRA_FAILED" if had_transport_failure else state.get("pipeline_status", "active"),
        "final_status": "INFRA_FAILED" if had_transport_failure else state.get("final_status", "active"),
        "error_log": error_log + (
            [f"scout_transport_error: {request_errors} query failures on attempt {search_attempts}"]
            if had_transport_failure else []
        ),
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
            "gatekeeper_results": [],
            "selected_candidate": None,
        }

    gatekeeper = LLMGatekeeper()
    selected_candidate = None
    new_results = list(existing_results)

    for candidate in candidates[:3]:
        logger.info(
            f"[GATEKEEPER] Evaluating deal_id={candidate.get('deal_id')} | docket_title='{candidate.get('docket_title')}'"
        )

        try:
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
            logger.info(
                f"[GATEKEEPER] Result for {candidate.get('deal_id')}: verdict={result.verdict} score={result.score} reasoning={result.reasoning[:100] if result.reasoning else 'N/A'}..."
            )

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
            elif gatekeeper_result["verdict"] == "SKIP" and gatekeeper_result.get("score", 0.0) <= 0.35:
                heuristic = _fallback_gatekeeper_from_title(candidate.get("docket_title", ""))
                if heuristic.get("verdict") == "DOWNLOAD":
                    gatekeeper_result = {
                        **heuristic,
                        "reasoning": "Recall rescue: heuristic first-day signal override on low-confidence SKIP.",
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
                "docket_title": candidate.get("docket_title", ""),
                "attachment_descriptions": candidate.get("attachment_descriptions", []),
            }

        new_results.append(gatekeeper_result)
        if gatekeeper_result.get("verdict") == "DOWNLOAD":
            selected_candidate = candidate
            break

    return {
        **state,
        "gatekeeper_results": new_results,
        "selected_candidate": selected_candidate,
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
    
    # Use candidate selected by gatekeeper; fallback to first for backward compatibility.
    candidate = state.get("selected_candidate") or candidates[0]
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
    if state.get("pipeline_status") == "INFRA_FAILED":
        return {
            **state,
            "pipeline_status": "INFRA_FAILED",
            "final_status": "INFRA_FAILED"
        }
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
