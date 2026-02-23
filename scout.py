"""
Scout module for Worktree A - Pure CourtListener RECAP API Pipeline

Implements the three-phase search:
1. Case lookup via docket search
2. Targeted docket entry search with keywords
3. RECAP document metadata extraction
"""
import asyncio
import json
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import aiolimiter

# Add the shared directory to the path
import sys
sys.path.insert(0, '../bankruptcy-retrieval')

from shared.config import (
    COURTLISTENER_API_TOKEN,
    COURTLISTENER_BASE_URL,
    COURTLISTENER_V4_SEARCH_URL,
    MAX_KEYWORD_QUERIES_PER_DEAL,
    get_court_slug
)
from config import RATE_LIMIT_STATE_FILE

# Exception for daily budget exhaustion
class DailyBudgetExhausted(Exception):
    """Raised when the daily API call budget is exhausted"""
    pass

# Rate limiting
rate_limiter = aiolimiter.AsyncLimiter(max_rate=10, time_period=1)

def load_rate_limit_state() -> Dict[str, Any]:
    """Load the rate limit state from file or initialize if not exists"""
    try:
        with open(RATE_LIMIT_STATE_FILE, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        return {
            "calls_today": 0,
            "reset_date": datetime.utcnow().strftime("%Y-%m-%d")
        }

def save_rate_limit_state(state: Dict[str, Any]) -> None:
    """Save the rate limit state to file"""
    with open(RATE_LIMIT_STATE_FILE, 'w') as f:
        json.dump(state, f)

def check_and_update_rate_limit() -> None:
    """Check and update the daily API call counter"""
    state = load_rate_limit_state()
    today = datetime.utcnow().strftime("%Y-%m-%d")

    # Reset counter if it's a new day
    if state["reset_date"] != today:
        state["calls_today"] = 0
        state["reset_date"] = today

    # Check if we've exceeded the daily limit
    if state["calls_today"] >= MAX_API_CALLS_PER_DAY:
        raise DailyBudgetExhausted(f"Daily API call budget of {MAX_API_CALLS_PER_DAY} exceeded")

    # Increment the counter
    state["calls_today"] += 1

    # Save the updated state
    save_rate_limit_state(state)

# HTTP client setup
http_client = httpx.AsyncClient(
    headers={"Authorization": f"Token {COURTLISTENER_API_TOKEN}"},
    timeout=30.0
)

# Retry configuration
retry_config = {
    "stop": stop_after_attempt(5),
    "wait": wait_exponential(multiplier=1, min=2, max=10),
    "retry": retry_if_exception_type((httpx.NetworkError, httpx.TimeoutException))
}

@retry(**retry_config)
async def rate_limited_api_call(url: str, params: Dict[str, Any]) -> httpx.Response:
    """Make a rate-limited API call to CourtListener"""
    # Check rate limits
    check_and_update_rate_limit()

    # Wait for per-second rate limiter
    await rate_limiter.acquire()

    # Make the API call
    response = await http_client.get(url, params=params)
    response.raise_for_status()
    return response

async def find_docket(company_name: str, filing_year: int, court: str, client: httpx.AsyncClient) -> Optional[Dict[str, Any]]:
    """
    Phase 1: Find the docket for a company's bankruptcy case.

    Args:
        company_name: Name of the company
        filing_year: Year of filing
        court: Court name (e.g., "S.D.N.Y.")
        client: HTTP client to use

    Returns:
        Docket data dict or None if not found
    """
    court_slug = get_court_slug(court)

    # Build query parameters for V4 search endpoint
    params = {
        "q": f'"{company_name}" chapter:11',
        "type": "r",  # docket type
        "available_only": "on",
        "order_by": "score desc",
        "filed_after": f"{filing_year}-01-01",
        "filed_before": f"{filing_year}-12-31",
    }

    # Add court filter if we have a valid slug
    if court_slug:
        params["court"] = court_slug

    url = COURTLISTENER_V4_SEARCH_URL

    try:
        response = await rate_limited_api_call(url, params)
        data = response.json()

        # Return the first result if any found
        if data.get("results"):
            return data["results"][0]
        return None
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return None
        raise
    except DailyBudgetExhausted:
        raise
    except Exception:
        return None

async def find_docket_entries(docket_id: str, keywords: List[str], client: httpx.AsyncClient) -> List[Dict[str, Any]]:
    """
    Phase 2: Find docket entries matching priority keywords.

    Args:
        docket_id: The docket ID to search within
        keywords: List of keywords to search for (in priority order)
        client: HTTP client to use

    Returns:
        List of matching docket entries
    """
    found_entries = []
    queries_made = 0

    for keyword in keywords[:MAX_KEYWORD_QUERIES_PER_DEAL]:
        if queries_made >= MAX_KEYWORD_QUERIES_PER_DEAL:
            break

        # Build query for V4 search endpoint
        # Search within the specific docket by its ID in the query
        params = {
            "q": f'docket_id:{docket_id} "{keyword}"',
            "type": "r",  # docket type
            "available_only": "on",
            "order_by": "score desc",
            "filed_after": "2019-01-01",  # Broad range to catch older cases
        }

        url = COURTLISTENER_V4_SEARCH_URL

        try:
            response = await rate_limited_api_call(url, params)
            queries_made += 1

            data = response.json()
            results = data.get("results", [])

            # Add entries to our found list
            for entry in results:
                # Only add if we haven't seen this entry ID before
                if not any(e.get("id") == entry.get("id") for e in found_entries):
                    found_entries.append(entry)

            # If we found entries, we might have what we need
            if results:
                # For now, we'll return what we have - in a real implementation,
                # we might want to continue searching for better matches
                pass

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 404:
                continue
            raise
        except DailyBudgetExhausted:
            raise
        except Exception:
            # Continue with next keyword on any other error
            continue

    return found_entries

async def get_recap_document_metadata(doc_id: str, client: httpx.AsyncClient) -> Optional[Dict[str, Any]]:
    """
    Phase 3: Get metadata for a RECAP document.

    Args:
        doc_id: The docket entry ID
        client: HTTP client to use

    Returns:
        Document metadata dict or None if not found
    """
    # For V4, we'll use the BASE_URL for direct document lookup
    url = f"{COURTLISTENER_BASE_URL}/recap-documents/{doc_id}/"
    params = {
        "fields": "id,description,filepath_local,is_available"
    }

    try:
        response = await rate_limited_api_call(url, params)
        data = response.json()
        return data
    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            return None
        raise
    except DailyBudgetExhausted:
        raise
    except Exception:
        return None

# Close the HTTP client when done
async def close_http_client():
    """Close the HTTP client"""
    await http_client.aclose()