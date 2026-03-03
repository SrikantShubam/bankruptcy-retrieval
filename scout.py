"""
Scout module for Worktree A - Pure CourtListener RECAP API Pipeline

Implements the three-phase search:
1. Case lookup via docket search
2. Targeted docket entry search with keywords
3. RECAP document metadata extraction
"""
import asyncio
import json
import unicodedata
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
import httpx
from tenacity import retry, stop_after_attempt, wait_exponential, retry_if_exception_type
import aiolimiter

# Load environment variables first
from dotenv import load_dotenv
import os
load_dotenv('../.env')  # one level up

# Add the shared directory to the path
import sys
sys.path.insert(0, '../bankruptcy-retrieval')

from shared.config import (
    COURTLISTENER_BASE_URL,
    COURTLISTENER_V4_SEARCH_URL,
    MAX_KEYWORD_QUERIES_PER_DEAL,
    MAX_API_CALLS_PER_DAY,
    get_court_slug,
    PRIORITY_KEYWORDS
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

# Auth header function
async def get_auth_headers() -> dict:
    token = os.environ.get('COURTLISTENER_API_TOKEN')
    if not token:
        raise ValueError("COURTLISTENER_API_TOKEN not set in environment")
    return {"Authorization": f"Token {token}"}

def normalize_company_name(name: str) -> str:
    """
    Normalize company name for API queries.
    Handles special characters, smart quotes, em-dashes, etc.
    """
    # Normalize Unicode to NFC (composed) form
    name = unicodedata.normalize('NFC', name)
    
    # Replace common problematic characters with ASCII equivalents
    replacements = {
        '\u2013': '-',    # en-dash
        '\u2014': '-',    # em-dash
        '\u2018': "'",    # left single quote
        '\u2019': "'",    # right single quote
        '\u201c': '"',    # left double quote
        '\u201d': '"',    # right double quote
        '\u2010': '-',    # hyphen
        '\u2011': '-',    # non-breaking hyphen
    }
    
    for special, replacement in replacements.items():
        name = name.replace(special, replacement)
    
    return name

# Keywords to match inside recap_documents[].description
DOC_KEYWORDS = [
    "first day declaration",
    "declaration in support of first day",
    "declaration in support of chapter 11 petition",
    "declaration in support of the debtors",
    "in support of first day motions",
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
    "fee statement",
]
async def find_document_for_deal(
    company_name: str,
    filing_year: int,
    court: str,
) -> Optional[Dict[str, Any]]:
    """
    Search V4 for first day declaration using free-text queries,
    then filter recap_documents by description keyword.
    """
    SEARCH_URL = "https://www.courtlistener.com/api/rest/v4/search/"

    # Normalize company name to handle special characters
    clean_name = normalize_company_name(company_name)

    # Free-text queries — no field targeting, broader match
    QUERIES = [
        f'"{clean_name}" "first day"',
        f'"{clean_name}" "declaration in support"',
        f'"{clean_name}" "DIP motion"',
        f'"{clean_name}" "debtor in possession"',
        f'"{clean_name}" "cash collateral"',
    ]

    calls = 0
    for query in QUERIES[:MAX_KEYWORD_QUERIES_PER_DEAL]:
        params = {
            "q": query,
            "type": "r",
            "available_only": "on",
            "order_by": "score desc",
            "filed_after": f"{filing_year}-01-01",
            "filed_before": f"{filing_year}-12-31",
        }

        try:
            response = await rate_limited_api_call(SEARCH_URL, params)
            calls += 1
            data = response.json()
            results = data.get("results", [])

            for result in results:
                case_name = result.get("caseName", "")
                date_filed = (result.get("dateFiled") or "")[:10]

                for doc in result.get("recap_documents", []):
                    filepath = doc.get("filepath_local", "")
                    if not filepath or not doc.get("is_available", False):
                        continue

                    # Use full description for matching, short_description as title
                    description = doc.get("description", "").lower()
                    title = doc.get("description", "") or doc.get("short_description", "")

                    if not title or len(title) < 10:
                        continue

                    # Must match at least one positive keyword
                    has_signal = any(kw in description for kw in DOC_KEYWORDS)
                    is_noise = any(rj in description for rj in HARD_REJECT)

                    if not has_signal or is_noise:
                        continue

                    return {
                        "docket_entry_id": str(doc.get("docket_entry_id", doc.get("id", ""))),
                        "docket_title": title[:200],
                        "filing_date": doc.get("entry_date_filed") or date_filed,
                        "attachment_descriptions": [],
                        "resolved_pdf_url": f"https://storage.courtlistener.com/{filepath}",
                        "api_calls_consumed": calls,
                        "source": "courtlistener",
                    }

        except Exception as e:
            print(f"Query failed: {query[:50]} — {e}")
            continue

    return None
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

    # Get auth headers and make the API call
    headers = await get_auth_headers()
    async with httpx.AsyncClient(timeout=30.0) as client:
        response = await client.get(url, params=params, headers=headers)
        response.raise_for_status()
        return response


# Close the HTTP client when done
async def close_http_client():
    """Close the HTTP client - no-op since we use context managers now"""
    pass