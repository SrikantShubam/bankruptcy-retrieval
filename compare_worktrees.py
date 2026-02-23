"""
compare_worktrees.py
─────────────────────────────────────────────────────────────────────────────
Run this from the root bankruptcy-retrieval/ folder after all three worktrees
have completed their pipeline runs.

Usage:
    python compare_worktrees.py

It will look for benchmark_report.json in these locations:
    ../worktree-a/logs/benchmark_report.json
    ../worktree-b/logs/benchmark_report.json
    ../worktree-c/logs/benchmark_report.json

Prints a comparison table and declares a winner by F1 score.
Also flags any worktree that failed the exclusion audit.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import sys
from pathlib import Path


# ─────────────────────────────────────────────────────────────────────────────
# Config — where to find each report
# ─────────────────────────────────────────────────────────────────────────────

WORKTREE_REPORT_PATHS = {
    "A (RECAP API)":      Path("../worktree-a/logs/benchmark_report.json"),
    "B (Anti-Detect)":    Path("../worktree-b/logs/benchmark_report.json"),
    "C (Multi-Agent)":    Path("../worktree-c/logs/benchmark_report.json"),
}


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def load_report(path: Path) -> dict | None:
    if not path.exists():
        return None
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def fmt(value: float | int | None, decimals: int = 3) -> str:
    if value is None:
        return "N/A"
    if isinstance(value, float):
        return f"{value:.{decimals}f}"
    return str(value)


def exclusion_status(report: dict) -> str:
    bad = report.get("already_processed_incorrectly_processed", -1)
    ok  = report.get("already_processed_correctly_excluded", -1)
    if bad == 0:
        return f"✓ PASS ({ok}/5)"
    elif bad == -1:
        return "? UNKNOWN"
    else:
        return f"✗ FAIL ({bad} leaked)"


def integrity_check(report: dict) -> str:
    """Verify TP+FP+FN+TN+already == total deals."""
    tp      = report.get("true_positives", 0)
    fp      = report.get("false_positives", 0)
    fn      = report.get("false_negatives", 0)
    tn      = report.get("true_negatives", 0)
    already = report.get("deals_already_processed", 0)
    total   = report.get("deals_total", 0)
    actual  = tp + fp + fn + tn + already
    if total == 0:
        return "? NO DATA"
    return "✓ OK" if actual == total else f"✗ MISMATCH ({actual} vs {total})"


# ─────────────────────────────────────────────────────────────────────────────
# Main
# ─────────────────────────────────────────────────────────────────────────────

def main() -> None:
    reports: dict[str, dict | None] = {}
    for label, path in WORKTREE_REPORT_PATHS.items():
        reports[label] = load_report(path)

    available = {k: v for k, v in reports.items() if v is not None}
    missing   = [k for k, v in reports.items() if v is None]

    if not available:
        print("\n  No benchmark reports found yet.")
        print("  Run each worktree's main.py first, then re-run this script.\n")
        print("  Expected locations:")
        for label, path in WORKTREE_REPORT_PATHS.items():
            print(f"    {path.resolve()}")
        sys.exit(0)

    if missing:
        print(f"\n  ⚠  Missing reports for: {', '.join(missing)}")
        print("  Showing partial results for available worktrees.\n")

    labels = list(available.keys())
    data   = list(available.values())

    # ── Column widths ────────────────────────────────────────────────────────
    col_w = max(18, max(len(l) for l in labels) + 2)
    metric_w = 26

    def row(metric: str, values: list[str]) -> str:
        return f"  {metric:<{metric_w}}" + "".join(f"{v:^{col_w}}" for v in values)

    def divider() -> str:
        return "  " + "─" * (metric_w + col_w * len(labels))

    # ── Header ───────────────────────────────────────────────────────────────
    print()
    print("  " + "═" * (metric_w + col_w * len(labels)))
    print(f"  {'ARCHITECTURE BENCHMARK COMPARISON':^{metric_w + col_w * len(labels)}}")
    print("  " + "═" * (metric_w + col_w * len(labels)))
    print(row("Metric", labels))
    print(divider())

    # ── Core metrics ─────────────────────────────────────────────────────────
    print(row("F1 Score ★",          [fmt(r.get("f1_score"))         for r in data]))
    print(row("Precision",           [fmt(r.get("precision"))        for r in data]))
    print(row("Recall",              [fmt(r.get("recall"))           for r in data]))
    print(divider())
    print(row("True Positives",      [fmt(r.get("true_positives"),  0) for r in data]))
    print(row("False Positives",     [fmt(r.get("false_positives"), 0) for r in data]))
    print(row("False Negatives",     [fmt(r.get("false_negatives"), 0) for r in data]))
    print(row("True Negatives",      [fmt(r.get("true_negatives"),  0) for r in data]))
    print(divider())
    print(row("Decoy Filter Rate",   [fmt(r.get("decoy_filter_rate"))  for r in data]))
    print(row("API Efficiency",      [fmt(r.get("api_efficiency"), 4)  for r in data]))
    print(row("Total API Calls",     [fmt(r.get("total_api_calls"),  0) for r in data]))
    print(row("LLM Gatekeeper Calls",[fmt(r.get("total_llm_gatekeeper_calls"), 0) for r in data]))
    print(row("Runtime (seconds)",   [fmt(r.get("total_runtime_seconds"), 1) for r in data]))
    print(divider())

    # ── Audit rows ───────────────────────────────────────────────────────────
    print(row("Exclusion Audit",     [exclusion_status(r) for r in data]))
    print(row("Count Integrity",     [integrity_check(r)  for r in data]))
    print("  " + "═" * (metric_w + col_w * len(labels)))

    # ── Winner ───────────────────────────────────────────────────────────────
    # Disqualify any worktree that failed the exclusion audit
    qualified = [
        (label, r) for label, r in available.items()
        if r.get("already_processed_incorrectly_processed", 1) == 0
    ]
    disqualified = [
        label for label, r in available.items()
        if r.get("already_processed_incorrectly_processed", 1) != 0
    ]

    print()
    if disqualified:
        print(f"  ⚠  DISQUALIFIED (exclusion audit failure): {', '.join(disqualified)}")
        print("     These worktrees cannot be declared winner regardless of F1 score.")
        print()

    if not qualified:
        print("  ✗  No worktrees passed the exclusion audit. No winner declared.")
        print()
        return

    winner_label, winner_report = max(qualified, key=lambda x: x[1].get("f1_score", 0.0))
    winner_f1 = winner_report.get("f1_score", 0.0)

    print(f"  ★  WINNER BY F1 SCORE:  {winner_label}")
    print(f"     F1: {winner_f1:.4f}  |  "
          f"P: {winner_report.get('precision', 0):.4f}  |  "
          f"R: {winner_report.get('recall', 0):.4f}")

    # ── Runner-up gap ─────────────────────────────────────────────────────────
    others = [(l, r) for l, r in qualified if l != winner_label]
    if others:
        second_label, second_report = max(others, key=lambda x: x[1].get("f1_score", 0.0))
        gap = winner_f1 - second_report.get("f1_score", 0.0)
        print(f"     Runner-up: {second_label}  (gap: {gap:+.4f} F1 points)")

    print()

    # ── Hybrid recommendation check ───────────────────────────────────────────
    if len(qualified) >= 2:
        f1_scores = {l: r.get("f1_score", 0.0) for l, r in qualified}
        recalls   = {l: r.get("recall", 0.0)   for l, r in qualified}

        best_recall_label = max(recalls, key=recalls.get)
        best_f1_label     = max(f1_scores, key=f1_scores.get)

        recall_gap = recalls[best_recall_label] - recalls[best_f1_label]
        if best_recall_label != best_f1_label and recall_gap > 0.05:
            print(f"  💡 HYBRID SUGGESTION:")
            print(f"     {best_recall_label} has higher recall (+{recall_gap:.3f}).")
            print(f"     Consider using {best_f1_label} as primary pipeline and")
            print(f"     {best_recall_label} as fallback for deals not found by primary.")
            print()

    # ── Next step hint ────────────────────────────────────────────────────────
    print("  Next step: feed the three execution_log.jsonl files and this output")
    print("  to the EVALUATOR_PROMPT_CODEX.md prompt for deep qualitative analysis.")
    print()


if __name__ == "__main__":
    main()