import json
import os
import time
from dataclasses import dataclass, field
from typing import Any, Dict, List


TERMINAL_STATUSES = {
    "DOWNLOADED",
    "NOT_FOUND",
    "SKIPPED",
    "FETCH_FAILED",
    "INFRA_FAILED",
    "ALREADY_PROCESSED",
}


@dataclass
class TelemetryCollector:
    log_path: str = "logs/execution_log.jsonl"
    report_path: str = "logs/benchmark_report.json"
    start_time: float = field(default_factory=time.time)
    events: List[Dict[str, Any]] = field(default_factory=list)

    def record_terminal(self, event: Dict[str, Any]) -> None:
        status = event.get("pipeline_status")
        if status not in TERMINAL_STATUSES:
            raise ValueError(f"Invalid terminal status: {status}")
        self.events.append(event)

    def _safe_div(self, a: float, b: float) -> float:
        return a / b if b else 0.0

    def _classify(self, truth: Dict[str, Any], status: str) -> str:
        if truth.get("already_processed", False):
            return "ALREADY_PROCESSED"
        has_data = bool(truth.get("has_financial_data", False))
        if status == "DOWNLOADED":
            return "TP" if has_data else "FP"
        if status in ("SKIPPED", "NOT_FOUND"):
            return "FN" if has_data else "TN"
        if status == "FETCH_FAILED":
            return "FN" if has_data else "TN"
        if status == "INFRA_FAILED":
            return "UNCLASSIFIED"
        return "UNCLASSIFIED"

    def summarize(self, ground_truth: Dict[str, Dict[str, Any]], total_api_calls: int, total_llm_calls: int) -> Dict[str, Any]:
        tp = fp = fn = tn = infra_failed = already = unclassified = 0
        statuses_by_deal = {str(e["deal_id"]): e["pipeline_status"] for e in self.events}

        for deal_id, status in statuses_by_deal.items():
            truth = ground_truth.get(deal_id)
            if truth is None:
                truth = {"has_financial_data": False, "already_processed": False}
                unclassified += 1
            cls = self._classify(truth, status)
            if cls == "TP":
                tp += 1
            elif cls == "FP":
                fp += 1
            elif cls == "FN":
                fn += 1
            elif cls == "TN":
                tn += 1
            elif cls == "ALREADY_PROCESSED":
                already += 1
            elif cls == "UNCLASSIFIED":
                unclassified += 1

            if status == "INFRA_FAILED":
                infra_failed += 1

        precision = self._safe_div(tp, tp + fp)
        recall = self._safe_div(tp, tp + fn)
        f1_score = self._safe_div(2 * precision * recall, precision + recall)

        active = tp + fp + fn + tn
        coverage = self._safe_div(tp + fp, active)
        decoy_filter_rate = self._safe_div(tn, tn + fp)
        api_efficiency = self._safe_div(tp, total_api_calls)

        return {
            "TP": tp,
            "FP": fp,
            "FN": fn,
            "TN": tn,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1_score, 4),
            "coverage": round(coverage, 4),
            "decoy_filter_rate": round(decoy_filter_rate, 4),
            "api_efficiency": round(api_efficiency, 6),
            "infra_failed": infra_failed,
            "total_api_calls": total_api_calls,
            "total_llm_gatekeeper_calls": total_llm_calls,
            "total_runtime_seconds": round(time.time() - self.start_time, 2),
            "deals_total": len(statuses_by_deal),
            "deals_active": active,
            "deals_already_processed": already,
            "unclassified": unclassified,
            "true_positives": tp,
            "false_positives": fp,
            "false_negatives": fn,
            "true_negatives": tn,
        }

    def flush(self, report: Dict[str, Any]) -> None:
        os.makedirs(os.path.dirname(self.log_path), exist_ok=True)
        with open(self.log_path, "w", encoding="utf-8") as f:
            for e in self.events:
                f.write(json.dumps(e) + "\n")
        with open(self.report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
