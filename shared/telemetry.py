"""
shared/telemetry.py
─────────────────────────────────────────────────────────────────────────────
Telemetry, execution logging, and F1 benchmark scoring.

All three worktrees use this module identically.

Responsibilities:
  • Append structured JSON events to execution_log.jsonl (append-only)
  • Classify pipeline outcomes against ground_truth.json
  • Calculate Precision, Recall, F1, Decoy Filter Rate, API Efficiency
  • Write benchmark_report.json at end of pipeline run
  • Expose simple log_*() helper methods so worktree code stays clean

Schema reference: see TELEMETRY_AND_LOGGING.md
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass, asdict, field
from pathlib import Path
from typing import Any, Literal

logger = logging.getLogger(__name__)

# Pipeline status literals (mirrors shared/config.py PipelineStatus)
_STATUS = Literal[
    "ALREADY_PROCESSED", "DOWNLOADED", "SKIPPED",
    "NOT_FOUND", "FETCH_FAILED", "PENDING"
]


# ─────────────────────────────────────────────────────────────────────────────
# Internal event dataclass
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class _LogEvent:
    event_type: str
    worktree: str
    deal_id: str
    company_name: str
    timestamp_utc: str
    elapsed_seconds: float
    # All extra fields are stored in payload and merged on serialisation
    payload: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        base = {
            "event_type":     self.event_type,
            "worktree":       self.worktree,
            "deal_id":        self.deal_id,
            "company_name":   self.company_name,
            "timestamp_utc":  self.timestamp_utc,
            "elapsed_seconds": round(self.elapsed_seconds, 4),
        }
        base.update(self.payload)
        return base


# ─────────────────────────────────────────────────────────────────────────────
# TelemetryLogger
# ─────────────────────────────────────────────────────────────────────────────

class TelemetryLogger:
    """
    Central logger for a single pipeline run.

    Instantiate once at the start of main.py:

        telemetry = TelemetryLogger(
            worktree="A",
            ground_truth_path="../bankruptcy-retrieval/data/ground_truth.json",
            log_dir="./logs",
        )

    Then call log_*() helpers throughout the pipeline.
    Call telemetry.finalise() at the very end to write benchmark_report.json.
    """

    def __init__(
        self,
        worktree: str,
        ground_truth_path: str,
        log_dir: str = "./logs",
    ):
        self.worktree = worktree.upper()
        self.log_dir  = Path(log_dir)
        self.log_dir.mkdir(parents=True, exist_ok=True)

        self.log_path    = self.log_dir / "execution_log.jsonl"
        self.report_path = self.log_dir / "benchmark_report.json"

        # Load ground truth
        gt_path = Path(ground_truth_path)
        if not gt_path.exists():
            raise FileNotFoundError(
                f"[TelemetryLogger] ground_truth.json not found at {gt_path}. "
                "Make sure the data/ folder is populated."
            )
        with open(gt_path, encoding="utf-8") as f:
            self.ground_truth: dict[str, dict] = json.load(f)

        # Runtime tracking
        self._pipeline_start: float = time.time()
        self._deal_start:     dict[str, float] = {}   # deal_id → start timestamp
        self._api_calls_total: int = 0
        self._llm_calls_total: int = 0

        # Final outcome registry  deal_id → pipeline_status string
        self._outcomes: dict[str, str] = {}

    # ──────────────────────────────────────────────────────────────────────
    # Deal lifecycle helpers
    # ──────────────────────────────────────────────────────────────────────

    def start_deal(self, deal_id: str) -> None:
        """Call at the very start of processing each deal."""
        self._deal_start[deal_id] = time.time()

    def _elapsed(self, deal_id: str) -> float:
        return time.time() - self._deal_start.get(deal_id, self._pipeline_start)

    def _now_iso(self) -> str:
        from datetime import datetime, timezone
        return datetime.now(timezone.utc).isoformat(timespec="milliseconds")

    def _append(self, event: _LogEvent) -> None:
        """Append a single JSON line to execution_log.jsonl."""
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event.to_dict(), ensure_ascii=False) + "\n")

    def _make_event(
        self,
        event_type: str,
        deal: dict,
        extra: dict | None = None,
    ) -> _LogEvent:
        deal_id      = deal.get("deal_id", "unknown")
        company_name = deal.get("company_name", "unknown")
        return _LogEvent(
            event_type=event_type,
            worktree=self.worktree,
            deal_id=deal_id,
            company_name=company_name,
            timestamp_utc=self._now_iso(),
            elapsed_seconds=self._elapsed(deal_id),
            payload=extra or {},
        )

    # ──────────────────────────────────────────────────────────────────────
    # Structured log helpers (one per event type in the schema)
    # ──────────────────────────────────────────────────────────────────────

    def log_exclusion_skip(self, deal: dict) -> None:
        """Log an EXCLUSION_SKIP event.  Must be the ONLY event for this deal."""
        event = self._make_event(
            "EXCLUSION_SKIP", deal,
            extra={"reason": "already_processed", "api_calls_consumed": 0}
        )
        self._append(event)
        self._outcomes[deal.get("deal_id", "")] = "ALREADY_PROCESSED"

    def log_scout_query(
        self,
        deal: dict,
        source: str,
        query_params: dict,
        results_count: int,
        api_calls_this_query: int,
    ) -> None:
        self._api_calls_total += api_calls_this_query
        event = self._make_event(
            "SCOUT_QUERY", deal,
            extra={
                "source":                     source,
                "query_params":               query_params,
                "results_count":              results_count,
                "api_calls_consumed_this_query": api_calls_this_query,
                "api_calls_total":            self._api_calls_total,
            },
        )
        self._append(event)

    def log_gatekeeper_decision(
        self,
        deal: dict,
        docket_title: str,
        attachment_descriptions: list[str],
        llm_model: str,
        verdict: str,
        score: float,
        reasoning: str,
        token_count: int,
    ) -> None:
        self._llm_calls_total += 1
        event = self._make_event(
            "GATEKEEPER_DECISION", deal,
            extra={
                "docket_title":              docket_title,
                "attachment_descriptions":   attachment_descriptions[:5],
                "llm_model":                 llm_model,
                "llm_verdict":               verdict,
                "llm_score":                 round(score, 4),
                "llm_reasoning":             reasoning,
                "llm_tokens_used":           token_count,
            },
        )
        self._append(event)

    def log_fetch_result(
        self,
        deal: dict,
        success: bool,
        local_file_path: str | None,
        file_size_bytes: int | None,
        fetch_method: str,
        bot_bypass_used: bool = False,
        failure_reason: str | None = None,
    ) -> None:
        event = self._make_event(
            "FETCH_RESULT", deal,
            extra={
                "success":          success,
                "local_file_path":  local_file_path,
                "file_size_bytes":  file_size_bytes,
                "fetch_method":     fetch_method,
                "bot_bypass_used":  bot_bypass_used,
                "failure_reason":   failure_reason,
            },
        )
        self._append(event)

    def log_pipeline_terminal(
        self,
        deal: dict,
        pipeline_status: str,
        total_api_calls: int,
        total_llm_calls: int,
        downloaded_file: str | None = None,
    ) -> None:
        """
        MUST be called exactly once per deal, as the last event.
        Registers the final outcome for F1 classification.
        """
        deal_id = deal.get("deal_id", "unknown")
        self._outcomes[deal_id] = pipeline_status
        event = self._make_event(
            "PIPELINE_TERMINAL", deal,
            extra={
                "pipeline_status":       pipeline_status,
                "total_api_calls_this_deal": total_api_calls,
                "total_llm_calls_this_deal": total_llm_calls,
                "downloaded_file":       downloaded_file,
            },
        )
        self._append(event)

        # Update total API calls counter (only add if actual API calls were made)
        if total_api_calls > 0:
            self._api_calls_total += total_api_calls

    # Convenience pass-through events (Worktree B / C specific)

    def log_event(self, event_type: str, deal: dict, **kwargs: Any) -> None:
        """
        Generic log helper for worktree-specific events not covered above.
        Examples: cloudflare_challenge_detected, fallback_triggered,
                  session_health_check, validation_failure, agent_tool_call.
        """
        event = self._make_event(event_type, deal, extra=dict(kwargs))
        self._append(event)

    def log_budget_warning(self, api_calls_used: int) -> None:
        """Log a budget warning — not deal-specific."""
        record = {
            "event_type":      "BUDGET_WARNING",
            "worktree":        self.worktree,
            "deal_id":         None,
            "company_name":    None,
            "timestamp_utc":   self._now_iso(),
            "elapsed_seconds": round(time.time() - self._pipeline_start, 2),
            "api_calls_used":  api_calls_used,
            "remaining":       max(0, 4800 - api_calls_used),
        }
        with open(self.log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")

    # ──────────────────────────────────────────────────────────────────────
    # F1 Classification
    # ──────────────────────────────────────────────────────────────────────

    def classify(self, deal_id: str, pipeline_status: str) -> str:
        """
        Compare a pipeline outcome against ground_truth.json.

        Returns one of:
            "ALREADY_PROCESSED"
            "TRUE_POSITIVE"
            "FALSE_POSITIVE"
            "TRUE_NEGATIVE"
            "FALSE_NEGATIVE"
            "UNCLASSIFIED"  ← deal_id not in ground_truth (should not happen)
        """
        truth = self.ground_truth.get(deal_id)
        if truth is None:
            logger.warning("[Telemetry] deal_id '%s' not in ground_truth.json", deal_id)
            return "UNCLASSIFIED"

        if truth.get("already_processed", False):
            return "ALREADY_PROCESSED"

        has_data: bool = truth.get("has_financial_data", False)

        if pipeline_status == "DOWNLOADED":
            return "TRUE_POSITIVE" if has_data else "FALSE_POSITIVE"
        elif pipeline_status in ("SKIPPED", "NOT_FOUND"):
            return "TRUE_NEGATIVE" if not has_data else "FALSE_NEGATIVE"
        elif pipeline_status == "FETCH_FAILED":
            # Scout + Gatekeeper approved it, but download failed.
            # Treat as FALSE_NEGATIVE — we tried but couldn't get it.
            return "FALSE_NEGATIVE" if has_data else "TRUE_NEGATIVE"
        else:
            return "UNCLASSIFIED"

    # ──────────────────────────────────────────────────────────────────────
    # Final benchmark report
    # ──────────────────────────────────────────────────────────────────────

    def finalise(self) -> dict:
        """
        Classify all outcomes, compute F1 metrics, and write benchmark_report.json.
        Call this once at the very end of the pipeline run.

        Returns the report dict (also written to log_dir/benchmark_report.json).
        """
        tp = fp = fn = tn = already = unclassified = 0
        already_incorrectly_processed = 0

        for deal_id, status in self._outcomes.items():
            classification = self.classify(deal_id, status)
            if classification == "TRUE_POSITIVE":
                tp += 1
            elif classification == "FALSE_POSITIVE":
                fp += 1
            elif classification == "FALSE_NEGATIVE":
                fn += 1
            elif classification == "TRUE_NEGATIVE":
                tn += 1
            elif classification == "ALREADY_PROCESSED":
                already += 1
                # Check if we accidentally processed it (status != ALREADY_PROCESSED)
                if status != "ALREADY_PROCESSED":
                    already_incorrectly_processed += 1
            else:
                unclassified += 1

        # ── Metrics ────────────────────────────────────────────────────────
        precision = tp / (tp + fp) if (tp + fp) > 0 else 0.0
        recall    = tp / (tp + fn) if (tp + fn) > 0 else 0.0
        f1        = (
            2 * precision * recall / (precision + recall)
            if (precision + recall) > 0
            else 0.0
        )

        active_deals   = tp + fp + fn + tn
        coverage       = (tp + fp) / active_deals if active_deals > 0 else 0.0
        decoy_filter   = tn / (tn + fp) if (tn + fp) > 0 else 0.0
        api_efficiency = tp / self._api_calls_total if self._api_calls_total > 0 else 0.0

        total_runtime  = round(time.time() - self._pipeline_start, 2)

        report = {
            "worktree":                              self.worktree,
            "run_timestamp_utc":                     self._now_iso(),
            "deals_total":                           len(self._outcomes),
            "deals_already_processed":               already,
            "deals_active":                          active_deals,
            "true_positives":                        tp,
            "false_positives":                       fp,
            "true_negatives":                        tn,
            "false_negatives":                       fn,
            "unclassified":                          unclassified,
            "precision":                             round(precision, 4),
            "recall":                                round(recall, 4),
            "f1_score":                              round(f1, 4),
            "coverage":                              round(coverage, 4),
            "decoy_filter_rate":                     round(decoy_filter, 4),
            "api_efficiency":                        round(api_efficiency, 6),
            "total_api_calls":                       self._api_calls_total,
            "total_llm_gatekeeper_calls":            self._llm_calls_total,
            "total_runtime_seconds":                 total_runtime,
            "already_processed_correctly_excluded":  already - already_incorrectly_processed,
            "already_processed_incorrectly_processed": already_incorrectly_processed,
        }

        with open(self.report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)

        logger.info(
            "[Telemetry] Worktree %s — F1: %.3f | P: %.3f | R: %.3f | "
            "TP: %d FP: %d FN: %d TN: %d | runtime: %.1fs",
            self.worktree, f1, precision, recall, tp, fp, fn, tn, total_runtime,
        )

        if already_incorrectly_processed > 0:
            logger.error(
                "[Telemetry] ⚠ EXCLUSION BUG: %d already-processed deals were "
                "not correctly skipped!", already_incorrectly_processed,
            )

        return report

    # ──────────────────────────────────────────────────────────────────────
    # Convenience: print final summary to stdout
    # ──────────────────────────────────────────────────────────────────────

    def print_summary(self) -> None:
        """Pretty-print the benchmark report if it exists."""
        if not self.report_path.exists():
            print("[Telemetry] No report yet — call finalise() first.")
            return
        with open(self.report_path, encoding="utf-8") as f:
            report = json.load(f)
        print("\n" + "=" * 60)
        print(f"  WORKTREE {report['worktree']} — BENCHMARK RESULTS")
        print("=" * 60)
        print(f"  F1 Score  : {report['f1_score']:.4f}")
        print(f"  Precision : {report['precision']:.4f}")
        print(f"  Recall    : {report['recall']:.4f}")
        print(f"  TP / FP / FN / TN : "
              f"{report['true_positives']} / {report['false_positives']} / "
              f"{report['false_negatives']} / {report['true_negatives']}")
        print(f"  Decoy Filter Rate : {report['decoy_filter_rate']:.4f}")
        print(f"  API Calls Total   : {report['total_api_calls']}")
        print(f"  Runtime           : {report['total_runtime_seconds']:.1f}s")
        excl_ok = report['already_processed_correctly_excluded']
        excl_bad = report['already_processed_incorrectly_processed']
        status = "✓ PASS" if excl_bad == 0 else f"✗ FAIL ({excl_bad} leaked through)"
        print(f"  Exclusion Audit   : {status}  ({excl_ok}/5 correctly skipped)")
        print("=" * 60 + "\n")
