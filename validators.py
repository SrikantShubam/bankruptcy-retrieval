"""
validators.py
─────────────────────────────────────────────────────────────────────────────
Pydantic schemas for all agent outputs in Worktree C.

Every agent output must pass validation before state update.
If validation fails: log validation_failure event, increment search_attempts,
return current state unchanged (Rule 3).

Schema reference: WORKTREE_C_MULTI_AGENT.md §9
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import re
from typing import Literal, Optional

from pydantic import BaseModel, Field, field_validator


# ─────────────────────────────────────────────────────────────────────────────
# Valid PDF Domain Whitelist (anti-hallucination guard)
# ─────────────────────────────────────────────────────────────────────────────

VALID_PDF_DOMAIN_PATTERNS: list[str] = [
    r"kroll\.com",
    r"cases\.stretto\.com",
    r"dm\.epiq11\.com",
    r"storage\.courtlistener\.com",
    r"ecf\.\w+\.uscourts\.gov",
    r"assets\.kroll\.com",
]


def _validate_url_domain(url: str | None) -> bool:
    """Check if URL matches one of the valid PDF domain patterns."""
    if not url:
        return True  # Allow null URLs
    return any(re.search(pattern, url) for pattern in VALID_PDF_DOMAIN_PATTERNS)


# ─────────────────────────────────────────────────────────────────────────────
# CandidateDocument Schema
# ─────────────────────────────────────────────────────────────────────────────

class CandidateDocument(BaseModel):
    """Schema for documents found by Scout agent."""
    deal_id: str
    source: Literal["courtlistener", "kroll", "stretto", "epiq"]
    docket_entry_id: str
    docket_title: str
    filing_date: str  # YYYY-MM-DD
    attachment_descriptions: list[str]
    resolved_pdf_url: Optional[str] = None
    api_calls_consumed: int = Field(ge=0)

    @field_validator("resolved_pdf_url")
    @classmethod
    def validate_pdf_url(cls, v: Optional[str]) -> Optional[str]:
        if v and not _validate_url_domain(v):
            raise ValueError(f"URL domain not in whitelist: {v}")
        return v

    @field_validator("filing_date")
    @classmethod
    def validate_date_format(cls, v: str) -> str:
        # Basic YYYY-MM-DD validation
        if not re.match(r"^\d{4}-\d{2}-\d{2}$", v):
            raise ValueError(f"Invalid date format: {v}. Expected YYYY-MM-DD")
        return v


# ─────────────────────────────────────────────────────────────────────────────
# Scout Agent Output Schema
# ─────────────────────────────────────────────────────────────────────────────

class ScoutOutput(BaseModel):
    """Schema for Scout agent output validation."""
    candidates: list[CandidateDocument]
    tool_calls_made: int = Field(ge=0, le=3)  # Hard cap at 3
    reasoning: str = Field(max_length=500)

    @field_validator("tool_calls_made")
    @classmethod
    def validate_tool_call_limit(cls, v: int) -> int:
        if v > 3:
            raise ValueError(f"Tool calls {v} exceeds maximum of 3")
        return v


# ─────────────────────────────────────────────────────────────────────────────
# Gatekeeper Agent Output Schema
# ─────────────────────────────────────────────────────────────────────────────

class GatekeeperOutput(BaseModel):
    """Schema for Gatekeeper agent output validation."""
    verdict: Literal["DOWNLOAD", "SKIP"]
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(max_length=200)
    token_count: int

    @field_validator("reasoning")
    @classmethod
    def validate_reasoning_not_empty(cls, v: str) -> str:
        if not v or not v.strip():
            raise ValueError("Reasoning cannot be empty")
        return v.strip()


# ─────────────────────────────────────────────────────────────────────────────
# Fetcher Agent Output Schema
# ─────────────────────────────────────────────────────────────────────────────

class FetcherOutput(BaseModel):
    """Schema for Fetcher agent output validation."""
    success: bool
    local_file_path: Optional[str] = None
    failure_reason: Optional[str] = None
    size_bytes: Optional[int] = Field(default=None, ge=0, le=52_428_800)  # 50MB max


# ─────────────────────────────────────────────────────────────────────────────
# Pipeline State Schema (for reference, used in graph.py)
# ─────────────────────────────────────────────────────────────────────────────

# PipelineState is defined in graph.py as a TypedDict
# This class provides type hints for validation purposes only
# (actual state is a dict, not a Pydantic model)
