"""
shared/config.py
─────────────────────────────────────────────────────────────────────────────
Shared constants used by all three worktrees.
All worktrees import from this file — do NOT duplicate these values locally.

Windows .env loading:
    All worktrees use find_root_env() from this module to locate the single
    .env file in the root repo regardless of working directory.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import os
from pathlib import Path
from dotenv import load_dotenv


# ─────────────────────────────────────────────────────────────────────────────
# .env Discovery (Windows-safe — no symlinks required)
# ─────────────────────────────────────────────────────────────────────────────

def find_root_env() -> Path:
    """
    Walk up the directory tree from this file's location to find the root
    .env file in the bankruptcy-retrieval repo.  Works on Windows, macOS,
    and Linux without requiring symlinks.

    Search order for each parent level:
      1. A .env sitting directly alongside this file's ancestor
      2. A .env inside a sibling folder named 'bankruptcy-retrieval'

    Raises FileNotFoundError if nothing is found within 6 levels.
    """
    current = Path(__file__).resolve().parent
    for _ in range(6):
        # Direct .env at this level
        candidate = current / ".env"
        if candidate.exists():
            return candidate
        # .env inside a sibling 'bankruptcy-retrieval' folder
        candidate = current.parent / "bankruptcy-retrieval" / ".env"
        if candidate.exists():
            return candidate
        current = current.parent
    raise FileNotFoundError(
        "Could not locate root .env file. "
        "Make sure bankruptcy-retrieval/.env exists and is populated."
    )


# Load the shared .env exactly once when this module is first imported
try:
    _env_path = find_root_env()
    load_dotenv(_env_path, override=False)  # override=False: don't stomp existing env vars
except FileNotFoundError as e:
    import warnings
    warnings.warn(f"[shared/config.py] {e}", stacklevel=2)


# ─────────────────────────────────────────────────────────────────────────────
# API Keys & Provider Settings (read from .env)
# ─────────────────────────────────────────────────────────────────────────────

COURTLISTENER_API_TOKEN: str = os.environ.get("COURTLISTENER_API_TOKEN", "")
OPENROUTER_API_KEY: str      = os.environ.get("OPENROUTER_API_KEY", "")
NVIDIA_NIM_API_KEY: str      = os.environ.get("NVIDIA_NIM_API_KEY", "")

GATEKEEPER_PROVIDER: str     = os.environ.get("GATEKEEPER_PROVIDER", "openrouter")
GATEKEEPER_MODEL_NIM: str    = os.environ.get("GATEKEEPER_MODEL", "meta/llama-3.1-8b-instruct")
GATEKEEPER_MODEL_OR: str     = os.environ.get("GATEKEEPER_MODEL", "meta-llama/llama-3.1-8b-instruct:free")

ORCHESTRATOR_MODEL: str      = os.environ.get(
    "ORCHESTRATOR_MODEL", "nvidia/llama-nemotron-nano-8b-instruct"
)

GATEKEEPER_SCORE_THRESHOLD: float = float(
    os.environ.get("GATEKEEPER_SCORE_THRESHOLD", "0.70")
)
MAX_API_CALLS_PER_DAY: int = int(
    os.environ.get("MAX_API_CALLS_PER_DAY", "4800")
)

DOWNLOAD_DIR: str = os.environ.get("DOWNLOAD_DIR", "./downloads")
LOG_DIR: str      = os.environ.get("LOG_DIR", "./logs")


# ─────────────────────────────────────────────────────────────────────────────
# The 5 Pre-Excluded Deals
# ─────────────────────────────────────────────────────────────────────────────
# These have already been manually processed.
# The pipeline must skip them BEFORE making any API call, browser launch,
# or LLM call.  Zero resource consumption for these five.

EXCLUDED_DEALS: frozenset[str] = frozenset({
    "Party City",
    "Diebold Nixdorf",
    "Incora",
    "Cano Health",
    "Envision Healthcare",
})

EXCLUDED_DEAL_IDS: frozenset[str] = frozenset({
    "party-city-2023",
    "diebold-nixdorf-2023",
    "incora-2023",
    "cano-health-2024",
    "envision-healthcare-2023",
})


def is_excluded(deal: dict) -> bool:
    """
    Return True if this deal should be skipped entirely.
    Checks both company_name and deal_id, and the already_processed flag.

    Usage:
        if is_excluded(deal):
            telemetry.log_already_processed(deal)
            continue
    """
    return (
        deal.get("company_name", "") in EXCLUDED_DEALS
        or deal.get("deal_id", "") in EXCLUDED_DEAL_IDS
        or deal.get("already_processed", False) is True
    )


# ─────────────────────────────────────────────────────────────────────────────
# Document Keyword Filters
# ─────────────────────────────────────────────────────────────────────────────
# Used by the Scout to filter docket entries server-side.
# Ordered by specificity — stop querying once the first match is found.

PRIORITY_KEYWORDS: list[str] = [
    "first day declaration",
    "declaration in support of first day",
    "DIP motion",
    "debtor in possession financing",
    "cash collateral",
    "capital structure",
    "prepetition debt",
    "credit agreement",
]

# Target document type labels (for display / logging)
TARGET_DOC_TYPES: list[str] = [
    "First Day Declaration",
    "DIP Motion",
    "Declaration in Support of First Day Motions",
    "Debtor in Possession Financing Motion",
    "Cash Collateral Motion",
]

# Maximum keyword queries the Scout may issue per deal before giving up
MAX_KEYWORD_QUERIES_PER_DEAL: int = 6

# Maximum PDF file size to download (50 MB).  Files larger than this are
# almost certainly full docket compilations, not individual motions.
MAX_PDF_BYTES: int = 52_428_800  # 50 MB

# CourtListener per-second rate limit
COURTLISTENER_REQUESTS_PER_SECOND: int = 10

# V4 REST API — filter-based, use for docket lookups by ID
# COURTLISTENER_BASE_URL: str = "https://www.courtlistener.com/api/rest/v4"
COURTLISTENER_V4_SEARCH_URL = "https://www.courtlistener.com/api/rest/v4/search/"
# KEEP — V4 REST filter endpoint (for direct ID lookups):
COURTLISTENER_BASE_URL = "https://www.courtlistener.com/api/rest/v4"
# V3 REST API — supports case_name__icontains, chapter, docket-entries filters
# Use this for all search operations (dockets, docket-entries, recap-documents)
COURTLISTENER_SEARCH_URL: str = "https://www.courtlistener.com/api/rest/v3"


# ─────────────────────────────────────────────────────────────────────────────
# Court Slug Mapping  (CourtListener uses short slugs, not full names)
# ─────────────────────────────────────────────────────────────────────────────

COURT_SLUG_MAP: dict[str, str] = {
    # Federal district courts most common in Ch11
    "S.D.N.Y.":   "nysd",
    "D.N.J.":     "njd",
    "D. Del.":    "deb",
    "D.D.C.":     "dcd",
    "S.D. Tex.":  "txsd",
    "N.D. Tex.":  "txnd",
    "E.D. Tex.":  "txed",
    "M.D. Fla.":  "flmd",
    "S.D. Fla.":  "flsd",
    "N.D. Ill.":  "ilnd",
    "E.D. Va.":   "vaed",
    "W.D. Va.":   "vaw",
    "S.D. Ind.":  "insd",
    "N.D. Cal.":  "cand",
    "C.D. Cal.":  "cacd",
    "S.D. Cal.":  "casd",
    "D. Md.":     "mdd",
    "D. Mass.":   "mad",
    "D. Conn.":   "ctd",
    "W.D.N.Y.":   "nywb",
    "E.D.N.Y.":   "nyed",
    "D.N.M.":     "nmd",
    "D. Nev.":    "nvd",
    "D. Ariz.":   "azd",
    "N.D. Ga.":   "gand",
    "D. Minn.":   "mnd",
    "E.D. Mo.":   "moed",
    "D. Kan.":    "ksd",
    "D. Colo.":   "cod",
    "W.D. Wash.": "wawd",
}


def get_court_slug(court_name: str | None) -> str | None:
    """
    Convert a human-readable court name to a CourtListener slug.
    Returns None if the court is unknown or None — callers should
    omit the 'court' filter from the API query in that case.

    Example:
        get_court_slug("S.D.N.Y.") → "nysd"
        get_court_slug(None)       → None
    """
    if not court_name:
        return None
    return COURT_SLUG_MAP.get(court_name.strip())


# ─────────────────────────────────────────────────────────────────────────────
# Valid PDF Domain Whitelist  (anti-hallucination guard for Worktree C)
# ─────────────────────────────────────────────────────────────────────────────

VALID_PDF_DOMAIN_PATTERNS: list[str] = [
    r"kroll\.com",
    r"cases\.stretto\.com",
    r"dm\.epiq11\.com",
    r"storage\.courtlistener\.com",
    r"ecf\.\w+\.uscourts\.gov",       # PACER / ECF direct (rare but valid)
    r"assets\.kroll\.com",
]


# ─────────────────────────────────────────────────────────────────────────────
# Claims Agent URL Patterns
# ─────────────────────────────────────────────────────────────────────────────

CLAIMS_AGENT_BASE_URLS: dict[str, str] = {
    "Kroll":    "https://www.kroll.com/en/services/restructuring/cases",
    "Stretto":  "https://cases.stretto.com",
    "Epiq":     "https://dm.epiq11.com",
    "Prime Clerk": "https://cases.primeclerk.com",  # legacy cases
}


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline Status Constants
# ─────────────────────────────────────────────────────────────────────────────
# Use these string literals everywhere — never hardcode status strings inline.

class PipelineStatus:
    ALREADY_PROCESSED = "ALREADY_PROCESSED"
    DOWNLOADED        = "DOWNLOADED"
    SKIPPED           = "SKIPPED"          # Gatekeeper rejected
    NOT_FOUND         = "NOT_FOUND"        # Scout found nothing
    FETCH_FAILED      = "FETCH_FAILED"     # Scout + Gatekeeper passed, download failed
    PENDING           = "PENDING"          # Initial state


class EventType:
    EXCLUSION_SKIP       = "EXCLUSION_SKIP"
    SCOUT_QUERY          = "SCOUT_QUERY"
    GATEKEEPER_DECISION  = "GATEKEEPER_DECISION"
    FETCH_RESULT         = "FETCH_RESULT"
    PIPELINE_TERMINAL    = "PIPELINE_TERMINAL"
    BUDGET_WARNING       = "BUDGET_WARNING"
    SESSION_HEALTH_CHECK = "SESSION_HEALTH_CHECK"
    CLOUDFLARE_CHALLENGE = "cloudflare_challenge_detected"
    CLOUDFLARE_BYPASS    = "cloudflare_bypass_success"
    FALLBACK_TRIGGERED   = "fallback_triggered"
    VALIDATION_FAILURE   = "validation_failure"
    AGENT_TOOL_CALL      = "agent_tool_call"
    TOKEN_BUDGET_EXCEEDED= "token_budget_exceeded"
