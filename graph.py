"""
graph.py
─────────────────────────────────────────────────────────────────────────────
LangGraph StateGraph definition for Worktree C.

Defines the state machine with all nodes and edges wired.
Uses stub nodes first (Rule 1), then replace with real logic in nodes.py.

Schema reference: WORKTREE_C_MULTI_AGENT.md §4
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

from typing import Optional

from langgraph.graph import StateGraph, END

# Import PipelineState from state_types.py to avoid circular imports
from state_types import PipelineState

# Import node functions (stubs for now)
from nodes import (
    exclusion_check_node,
    scout_node,
    gatekeeper_node,
    fetcher_node,
    fallback_node,
    log_node,
    telemetry_node,
)


# ─────────────────────────────────────────────────────────────────────────────
# Routing Functions
# ─────────────────────────────────────────────────────────────────────────────

def route_after_exclusion(state: PipelineState) -> str:
    """Route after exclusion check."""
    if state.get("pipeline_status") == "ALREADY_PROCESSED":
        return "already_processed"
    return "active"


def route_after_scout(state: PipelineState) -> str:
    """Route after Scout node execution."""
    candidates = state.get("candidates", [])
    search_attempts = state.get("search_attempts", 0)
    
    if candidates:
        return "found"
    if search_attempts < 3:
        return "retry"
    return "exhausted"


def route_after_gatekeeper(state: PipelineState) -> str:
    """Route after Gatekeeper evaluation."""
    results = state.get("gatekeeper_results", [])
    if not results:
        return "skip"  # No results means skip
    
    latest = results[-1]
    if latest.get("verdict") == "DOWNLOAD":
        return "download"
    return "skip"


def route_after_fetcher(state: PipelineState) -> str:
    """Route after Fetcher download attempt."""
    downloaded = state.get("downloaded_files", [])
    if downloaded:
        return "success"
    return "failed"


# ─────────────────────────────────────────────────────────────────────────────
# Build the StateGraph
# ─────────────────────────────────────────────────────────────────────────────

def build_graph() -> StateGraph:
    """
    Build and compile the LangGraph state machine.
    
    Flow:
    [START] → [exclusion_check] → (already_processed) → [log] → [END]
                           ↓ (active)
                      [scout] → (found) → [gatekeeper] → (download) → [fetcher] → (success) → [telemetry] → [END]
                           ↓ (retry/exhausted)         ↓ (skip)        ↓ (failed)
                          [scout]                      [log]          [fallback] → [telemetry] → [END]
    """
    graph = StateGraph(PipelineState)

    # ── Add all nodes ─────────────────────────────────────────────────────
    graph.add_node("exclusion_check", exclusion_check_node)
    graph.add_node("scout", scout_node)
    graph.add_node("gatekeeper", gatekeeper_node)
    graph.add_node("fetcher", fetcher_node)
    graph.add_node("fallback", fallback_node)
    graph.add_node("log", log_node)
    graph.add_node("telemetry", telemetry_node)

    # ── Set entry point ───────────────────────────────────────────────────
    graph.set_entry_point("exclusion_check")

    # ── Exclusion check routing ────────────────────────────────────────────
    graph.add_conditional_edges(
        "exclusion_check",
        route_after_exclusion,
        {
            "already_processed": "log",
            "active": "scout"
        }
    )

    # ── Scout routing — retry if no candidates, cap at 3 attempts ────────
    graph.add_conditional_edges(
        "scout",
        route_after_scout,
        {
            "found": "gatekeeper",
            "retry": "scout",
            "exhausted": "log"
        }
    )

    # ── Gatekeeper routing ────────────────────────────────────────────────
    graph.add_conditional_edges(
        "gatekeeper",
        route_after_gatekeeper,
        {
            "download": "fetcher",
            "skip": "log"
        }
    )

    # ── Fetcher routing ────────────────────────────────────────────────────
    graph.add_conditional_edges(
        "fetcher",
        route_after_fetcher,
        {
            "success": "telemetry",
            "failed": "fallback"
        }
    )

    # ── Terminal edges ────────────────────────────────────────────────────
    graph.add_edge("fallback", "telemetry")
    graph.add_edge("telemetry", END)
    graph.add_edge("log", END)

    return graph.compile()


# ─────────────────────────────────────────────────────────────────────────────
# Export for use in main.py
# ─────────────────────────────────────────────────────────────────────────────

__all__ = ["build_graph", "PipelineState"]
