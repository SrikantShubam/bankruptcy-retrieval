"""
types.py
─────────────────────────────────────────────────────────────────────────────
Shared type definitions for Worktree C.

This file contains the PipelineState TypedDict that is used by both
graph.py and nodes.py to avoid circular imports.

Schema reference: WORKTREE_C_MULTI_AGENT.md §3
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

from typing import TypedDict


class PipelineState(TypedDict):
    """
    State passed through the LangGraph pipeline.
    
    This is the single source of truth for state. Do not modify field names.
    """
    deal: dict                          # Current deal from dataset
    search_attempts: int                 # Counter: max 3 before NOT_FOUND
    candidates: list[dict]               # CandidateDocument list from Scout
    gatekeeper_results: list[dict]       # Gatekeeper verdict objects
    downloaded_files: list[str]          # Local file paths of successful downloads
    pipeline_status: str                 # Current status string
    api_calls_used: int                  # Running total across all agents
    orchestrator_tokens_used: int        # Token counter for orchestrator LLM
    error_log: list[str]                # Non-fatal errors (append only)
    final_status: str                   # Set once at terminal node


__all__ = ["PipelineState"]
