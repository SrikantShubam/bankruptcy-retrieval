"""
config.py
─────────────────────────────────────────────────────────────────────────────
Worktree C specific configuration constants.

This file contains constants specific to the LangGraph multi-agent pipeline.
Shared constants are in shared/config.py.

Schema reference: WORKTREE_C_MULTI_AGENT.md
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import os
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Import shared config and load .env
# ─────────────────────────────────────────────────────────────────────────────

# Import shared config (loads .env automatically)
from shared.config import (
    EXCLUDED_DEALS,
    EXCLUDED_DEAL_IDS,
    is_excluded,
    GATEKEEPER_SCORE_THRESHOLD,
    DOWNLOAD_DIR,
    VALID_PDF_DOMAIN_PATTERNS,
)

# Also import these for direct access
from shared.config import (
    COURTLISTENER_API_TOKEN,
    OPENROUTER_API_KEY,
    NVIDIA_NIM_API_KEY,
)


# ─────────────────────────────────────────────────────────────────────────────
# Orchestrator LLM Configuration
# ─────────────────────────────────────────────────────────────────────────────

# Default to using OpenRouter for the orchestrator
ORCHESTRATOR_MODEL: str = os.environ.get(
    "ORCHESTRATOR_MODEL", "meta-llama/llama-3.1-8b-instruct:free"
)

ORCHESTRATOR_PROVIDER: str = os.environ.get(
    "ORCHESTRATOR_PROVIDER", "openrouter"
)

# Max tokens for orchestrator LLM per deal (Rule 4)
MAX_ORCHESTRATOR_TOKENS_PER_DEAL: int = int(
    os.environ.get("MAX_ORCHESTRATOR_TOKENS_PER_DEAL", "2000")
)

# Max tool calls per deal (enforced by graph edges, not prompt)
MAX_TOOL_CALLS_PER_DEAL: int = 3

# Max search attempts before giving up
MAX_SEARCH_ATTEMPTS: int = 3


# ─────────────────────────────────────────────────────────────────────────────
# Browser Configuration
# ─────────────────────────────────────────────────────────────────────────────

USE_BROWSER: bool = os.environ.get("USE_BROWSER", "true").lower() == "true"

BROWSER_HEADLESS: bool = os.environ.get("BROWSER_HEADLESS", "true").lower() == "true"

# Browser-Use task prompt template
BROWSER_USE_TASK_TEMPLATE: str = """
Navigate to the {claims_agent} case search page and find documents for
"{company_name}" filed in {filing_year}.

Find documents with these titles (any one is sufficient):
- "First Day Declaration" or "Declaration in Support of First Day Motions"
- "DIP Motion" or "Debtor in Possession Financing Motion"

Extract ONLY: document title, filing date, PDF URL.
Do NOT click any download link.
Do NOT navigate away from the case page.
Return results as JSON only. No explanation text.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Scout Agent System Prompt
# ─────────────────────────────────────────────────────────────────────────────

SCOUT_SYSTEM_PROMPT: str = """\
You are a Scout agent retrieving Chapter 11 bankruptcy documents.

DEAL: {deal_json}

YOUR GOAL: Find a CandidateDocument containing a First Day Declaration or DIP Motion
for this company. Return a list of CandidateDocument objects.

RULES:
1. Use search_courtlistener_api FIRST. It is fastest and most reliable.
2. Only use search_claims_agent_browser if CourtListener returns no results.
3. Only use search_courtlistener_text as a last resort.
4. Maximum 3 total tool calls. If no results after 3 calls, return empty list.
5. DO NOT fabricate document URLs. Only return URLs from tool results.
6. DO NOT call any tool not in your tool list.
7. Return ONLY valid JSON matching the CandidateDocument schema.

FORBIDDEN: Do not attempt to read PDFs. Do not invent docket entry IDs.
"""


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline State Constants
# ─────────────────────────────────────────────────────────────────────────────

class PipelineStatus:
    """Pipeline status constants."""
    ALREADY_PROCESSED = "ALREADY_PROCESSED"
    DOWNLOADED = "DOWNLOADED"
    SKIPPED = "SKIPPED"
    NOT_FOUND = "NOT_FOUND"
    FETCH_FAILED = "FETCH_FAILED"
    PENDING = "PENDING"


# ─────────────────────────────────────────────────────────────────────────────
# Logging Configuration
# ─────────────────────────────────────────────────────────────────────────────

LOG_DIR: str = os.environ.get("LOG_DIR", "./logs")
LOG_FILE: str = os.environ.get("LOG_FILE", "execution_log.jsonl")

# Ensure log directory exists
Path(LOG_DIR).mkdir(parents=True, exist_ok=True)


# ─────────────────────────────────────────────────────────────────────────────
# Export all constants
# ─────────────────────────────────────────────────────────────────────────────

__all__ = [
    # Shared imports
    "EXCLUDED_DEALS",
    "EXCLUDED_DEAL_IDS",
    "is_excluded",
    "GATEKEEPER_SCORE_THRESHOLD",
    "DOWNLOAD_DIR",
    "VALID_PDF_DOMAIN_PATTERNS",
    "COURTLISTENER_API_TOKEN",
    "OPENROUTER_API_KEY",
    "NVIDIA_NIM_API_KEY",
    # Worktree C specific
    "ORCHESTRATOR_MODEL",
    "ORCHESTRATOR_PROVIDER",
    "MAX_ORCHESTRATOR_TOKENS_PER_DEAL",
    "MAX_TOOL_CALLS_PER_DEAL",
    "MAX_SEARCH_ATTEMPTS",
    "USE_BROWSER",
    "BROWSER_HEADLESS",
    "BROWSER_USE_TASK_TEMPLATE",
    "SCOUT_SYSTEM_PROMPT",
    "PipelineStatus",
    "LOG_DIR",
    "LOG_FILE",
]
