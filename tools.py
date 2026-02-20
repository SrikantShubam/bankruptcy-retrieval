"""
tools.py
─────────────────────────────────────────────────────────────────────────────
Tool definitions for the Scout agent.

These are the three tools the Scout agent can invoke:
1. search_courtlistener_api - CourtListener RECAP API search
2. search_claims_agent_browser - Browser-Use powered claims agent search
3. search_courtlistener_fulltext - Full-text search on CourtListener

Schema reference: WORKTREE_C_MULTI_AGENT.md §5
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import logging
import re
from typing import Any

import httpx
from langchain_core.tools import tool

from shared.config import (
    COURTLISTENER_API_TOKEN,
    COURTLISTENER_BASE_URL,
    CLAIMS_AGENT_BASE_URLS,
    VALID_PDF_DOMAIN_PATTERNS,
)
from validators import CandidateDocument

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# URL Domain Validation (anti-hallucination)
# ─────────────────────────────────────────────────────────────────────────────

def validate_url_domain(url: str | None) -> bool:
    """Check if URL matches one of the valid PDF domain patterns."""
    if not url:
        return True
    return any(re.search(pattern, url) for pattern in VALID_PDF_DOMAIN_PATTERNS)


# ─────────────────────────────────────────────────────────────────────────────
# Tool 1: CourtListener API Search
# ─────────────────────────────────────────────────────────────────────────────

@tool
async def search_courtlistener_api(
    company_name: str,
    filing_year: int,
    court: str | None = None,
    keyword: str = "first day declaration"
) -> str:
    """
    Search CourtListener RECAP API for docket entries matching the keyword.
    
    Returns JSON string of CandidateDocument list. Returns empty list if not found.
    Consumes 1-3 API calls.
    
    Args:
        company_name: Company name to search for
        filing_year: Year of filing
        court: Court abbreviation (e.g., 'S.D.N.Y.' -> 'nysd')
        keyword: Search keyword (default: 'first day declaration')
    """
    from shared.config import get_court_slug
    
    # Convert court name to slug
    court_slug = get_court_slug(court)
    
    # Build query parameters
    params = {
        "case_name__icontains": company_name,
        "docket_entry__date_filed__gte": f"{filing_year}-01-01",
        "docket_entry__date_filed__lte": f"{filing_year}-12-31",
        "docket_entry__description__icontains": keyword,
        "format": "json",
        "limit": 10,
    }
    
    if court_slug:
        params["docket__court"] = court_slug
    
    headers = {}
    if COURTLISTENER_API_TOKEN:
        headers["Authorization"] = f"Token {COURTLISTENER_API_TOKEN}"
    
    candidates = []
    api_calls = 0
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            # First, search for the docket
            docket_params = {
                "case_name__icontains": company_name,
                "date_filed__gte": f"{filing_year}-01-01",
                "date_filed__lte": f"{filing_year}-12-31",
                "format": "json",
                "limit": 5,
            }
            if court_slug:
                docket_params["court"] = court_slug
            
            response = await client.get(
                f"{COURTLISTENER_BASE_URL}/dockets/",
                params=docket_params,
                headers=headers
            )
            api_calls += 1
            
            if response.status_code == 200:
                docket_data = response.json()
                results = docket_data.get("results", [])
                
                for docket in results:
                    docket_id = docket.get("id")
                    if not docket_id:
                        continue
                    
                    # Get docket entries for this docket
                    entries_response = await client.get(
                        f"{COURTLISTENER_BASE_URL}/docket-entries/",
                        params={
                            "docket": docket_id,
                            "docket_entry__description__icontains": keyword,
                            "format": "json",
                            "limit": 10,
                        },
                        headers=headers
                    )
                    api_calls += 1
                    
                    if entries_response.status_code == 200:
                        entries_data = entries_response.json()
                        for entry in entries_data.get("results", []):
                            description = entry.get("description", "")
                            if not description:
                                continue
                            
                            # Check for PDF URL
                            pdf_url = None
                            attachments = entry.get("attachment", [])
                            for att in attachments:
                                if att.get("pdf_url"):
                                    pdf_url = att.get("pdf_url")
                                    break
                            
                            if pdf_url and not validate_url_domain(pdf_url):
                                logger.warning(f"URL domain not in whitelist: {pdf_url}")
                                continue
                            
                            candidate = {
                                "deal_id": f"{company_name.lower().replace(' ', '-')}-{filing_year}",
                                "source": "courtlistener",
                                "docket_entry_id": str(entry.get("id", "")),
                                "docket_title": description,
                                "filing_date": entry.get("date_filed", "")[:10],
                                "attachment_descriptions": [
                                    a.get("description", "") for a in attachments[:5]
                                ],
                                "resolved_pdf_url": pdf_url,
                                "api_calls_consumed": api_calls,
                            }
                            candidates.append(candidate)
    
    except Exception as e:
        logger.warning(f"CourtListener API error: {e}")
    
    return json.dumps(candidates)


# ─────────────────────────────────────────────────────────────────────────────
# Tool 2: Claims Agent Browser Search (Browser-Use)
# ─────────────────────────────────────────────────────────────────────────────

@tool
async def search_claims_agent_browser(
    company_name: str,
    claims_agent: str
) -> str:
    """
    Use Browser-Use to navigate the specified claims agent website.
    
    Returns JSON string of CandidateDocument list. Returns empty list if not found.
    Only call if search_courtlistener_api returned no results.
    
    Args:
        company_name: Company name to search for
        claims_agent: Claims agent name (Kroll, Stretto, Epiq)
    """
    # This is a placeholder that will be replaced with actual Browser-Use
    # implementation. For now, return empty results.
    logger.info(f"Browser-Use search for {company_name} via {claims_agent}")
    
    # The actual Browser-Use implementation will be in the Scout agent
    # This tool just returns the search results after browser automation
    return json.dumps([])


# ─────────────────────────────────────────────────────────────────────────────
# Tool 3: CourtListener Full-Text Search
# ─────────────────────────────────────────────────────────────────────────────

@tool
async def search_courtlistener_fulltext(query: str) -> str:
    """
    Full-text search on CourtListener /api/rest/v3/search/.
    
    Last resort only. Consumes 1 API call.
    
    Args:
        query: Full-text search query
    """
    headers = {}
    if COURTLISTENER_API_TOKEN:
        headers["Authorization"] = f"Token {COURTLISTENER_API_TOKEN}"
    
    candidates = []
    api_calls = 0
    
    try:
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{COURTLISTENER_BASE_URL}/search/",
                params={
                    "q": query,
                    "format": "json",
                    "type": "docket",
                    "limit": 10,
                },
                headers=headers
            )
            api_calls += 1
            
            if response.status_code == 200:
                data = response.json()
                for result in data.get("results", []):
                    docket = result.get("docket", {})
                    if not docket:
                        continue
                    
                    candidate = {
                        "deal_id": f"{query.split()[0].lower()}-search",
                        "source": "courtlistener",
                        "docket_entry_id": str(docket.get("id", "")),
                        "docket_title": docket.get("case_name", ""),
                        "filing_date": docket.get("date_filed", "")[:10] if docket.get("date_filed") else "",
                        "attachment_descriptions": [],
                        "resolved_pdf_url": None,
                        "api_calls_consumed": api_calls,
                    }
                    candidates.append(candidate)
    
    except Exception as e:
        logger.warning(f"CourtListener full-text search error: {e}")
    
    return json.dumps(candidates)


# ─────────────────────────────────────────────────────────────────────────────
# Export all tools
# ─────────────────────────────────────────────────────────────────────────────

__all__ = [
    "search_courtlistener_api",
    "search_claims_agent_browser",
    "search_courtlistener_fulltext",
]
