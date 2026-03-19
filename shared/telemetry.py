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

    def _normalize_doc_type(self, value: str) -> str:
        lowered = (value or "").strip().lower()
        if not lowered:
            return ""
        if lowered in {"dip_motion", "first_day_declaration", "cash_collateral_motion", "credit_agreement"}:
            return lowered
        if "credit agreement" in lowered:
            return "credit_agreement"
        if any(token in lowered for token in ("debtor in possession", "dip motion", "postpetition financing", "dip financing")):
            return "dip_motion"
        if "cash collateral" in lowered:
            return "cash_collateral_motion"
        if "interim" in lowered and "dip" in lowered and "order" in lowered:
            return "interim_dip_order"
        if "sale motion" in lowered:
            return "sale_motion"
        if ("declaration" in lowered or "affidavit" in lowered) and (
            "first day" in lowered or "chapter 11 petitions" in lowered or "first day pleadings" in lowered or "first day papers" in lowered
        ):
            return "first_day_declaration"
        return "other_supporting"

    def _required_types(self, truth: Dict[str, Any], event: Dict[str, Any]) -> List[str]:
        required: List[str] = []
        raw_required = truth.get("required_doc_types") or event.get("required_doc_types") or []
        if isinstance(raw_required, list):
            for value in raw_required:
                normalized = self._normalize_doc_type(str(value))
                if normalized and normalized not in required:
                    required.append(normalized)
        if not required:
            for key in ("expected_best_source_doc_type", "expected_doc_type"):
                normalized = self._normalize_doc_type(str(truth.get(key) or ""))
                if normalized and normalized not in required:
                    required.append(normalized)
        return required

    def _minimum_required_coverage(self, truth: Dict[str, Any], required: List[str]) -> int:
        configured = truth.get("minimum_required_coverage")
        if isinstance(configured, int) and configured > 0:
            return min(configured, len(required)) if required else configured
        if required:
            return len(required)
        return 1

    def _bundle_complete(self, truth: Dict[str, Any], event: Dict[str, Any]) -> bool:
        required = self._required_types(truth, event)
        selected_types = set()
        selected_documents = event.get("selected_documents", []) or []
        for document in selected_documents:
            if not document.get("same_case_confirmed", True):
                continue
            normalized = self._normalize_doc_type(str(document.get("normalized_doc_type") or ""))
            if normalized:
                selected_types.add(normalized)
        if not selected_types and not selected_documents:
            selected_types = {
                self._normalize_doc_type(str(t))
                for t in event.get("selected_doc_types", []) or []
            }
            selected_types.discard("")
            if not selected_types and event.get("selected_doc_type"):
                fallback = self._normalize_doc_type(str(event.get("selected_doc_type")))
                if fallback:
                    selected_types.add(fallback)
        if not required:
            return bool(selected_types)
        hits = sum(1 for doc_type in required if doc_type in selected_types)
        return hits >= self._minimum_required_coverage(truth, required)

    def _classify(self, truth: Dict[str, Any], event: Dict[str, Any]) -> str:
        status = str(event.get("pipeline_status") or "")
        if truth.get("already_processed", False):
            return "ALREADY_PROCESSED"
        has_data = bool(truth.get("has_financial_data", False))
        if status == "DOWNLOADED":
            if not has_data:
                return "FP"
            return "TP" if self._bundle_complete(truth, event) else "FN"
        if status in ("SKIPPED", "NOT_FOUND"):
            return "FN" if has_data else "TN"
        if status == "FETCH_FAILED":
            return "FN" if has_data else "TN"
        if status == "INFRA_FAILED":
            return "UNCLASSIFIED"
        return "UNCLASSIFIED"

    def summarize(self, ground_truth: Dict[str, Dict[str, Any]], total_api_calls: int, total_llm_calls: int) -> Dict[str, Any]:
        tp = fp = fn = tn = infra_failed = already = unclassified = 0
        incomplete_bundle_downloads = 0
        bundle_complete_deals = 0
        bundle_partial_deals = 0
        required_doc_type_hits = 0
        required_doc_type_total = 0
        selected_documents_total = 0
        tp_ids: List[str] = []
        fp_ids: List[str] = []
        fn_ids: List[str] = []
        tn_ids: List[str] = []
        events_by_deal = {str(e["deal_id"]): e for e in self.events}

        for deal_id, event in events_by_deal.items():
            selected_documents_total += len(event.get("selected_documents", []) or [])
            truth = ground_truth.get(deal_id)
            if truth is None:
                truth = {"has_financial_data": False, "already_processed": False}
                unclassified += 1
            cls = self._classify(truth, event)
            if cls == "TP":
                tp += 1
                tp_ids.append(deal_id)
                if event.get("pipeline_status") == "DOWNLOADED" and truth.get("has_financial_data", False):
                    bundle_complete_deals += 1
            elif cls == "FP":
                fp += 1
                fp_ids.append(deal_id)
            elif cls == "FN":
                fn += 1
                fn_ids.append(deal_id)
                if (
                    event.get("pipeline_status") == "DOWNLOADED"
                    and truth.get("has_financial_data", False)
                    and not self._bundle_complete(truth, event)
                ):
                    incomplete_bundle_downloads += 1
                    bundle_partial_deals += 1
            elif cls == "TN":
                tn += 1
                tn_ids.append(deal_id)
            elif cls == "ALREADY_PROCESSED":
                already += 1
            elif cls == "UNCLASSIFIED":
                unclassified += 1

            if event.get("pipeline_status") == "INFRA_FAILED":
                infra_failed += 1

            if truth.get("has_financial_data", False):
                required = self._required_types(truth, event)
                if required:
                    selected_types = set()
                    for document in event.get("selected_documents", []) or []:
                        if not document.get("same_case_confirmed", True):
                            continue
                        normalized = self._normalize_doc_type(str(document.get("normalized_doc_type") or ""))
                        if normalized:
                            selected_types.add(normalized)
                    if not selected_types and not (event.get("selected_documents", []) or []):
                        selected_types = {
                            self._normalize_doc_type(str(t))
                            for t in event.get("selected_doc_types", []) or []
                        }
                        selected_types.discard("")
                        if not selected_types and event.get("selected_doc_type"):
                            fallback = self._normalize_doc_type(str(event.get("selected_doc_type")))
                            if fallback:
                                selected_types.add(fallback)
                    required_doc_type_total += len(required)
                    required_doc_type_hits += sum(1 for doc_type in required if doc_type in selected_types)

        precision = self._safe_div(tp, tp + fp)
        recall = self._safe_div(tp, tp + fn)
        f1_score = self._safe_div(2 * precision * recall, precision + recall)

        active = tp + fp + fn + tn
        coverage = self._safe_div(tp + fp, active)
        decoy_filter_rate = self._safe_div(tn, tn + fp)
        api_efficiency = self._safe_div(tp, total_api_calls)
        required_doc_type_recall = self._safe_div(required_doc_type_hits, required_doc_type_total)
        bundle_complete_rate = self._safe_div(bundle_complete_deals, bundle_complete_deals + bundle_partial_deals)
        avg_selected_documents_per_active_deal = self._safe_div(selected_documents_total, active)

        return {
            "TP": tp,
            "FP": fp,
            "FN": fn,
            "TN": tn,
            "tp_deal_ids": tp_ids,
            "fp_deal_ids": fp_ids,
            "fn_deal_ids": fn_ids,
            "tn_deal_ids": tn_ids,
            "precision": round(precision, 4),
            "recall": round(recall, 4),
            "f1_score": round(f1_score, 4),
            "coverage": round(coverage, 4),
            "decoy_filter_rate": round(decoy_filter_rate, 4),
            "api_efficiency": round(api_efficiency, 6),
            "doc_type_mismatch_downloads": incomplete_bundle_downloads,
            "incomplete_bundle_downloads": incomplete_bundle_downloads,
            "bundle_complete_deals": bundle_complete_deals,
            "bundle_partial_deals": bundle_partial_deals,
            "bundle_complete_rate": round(bundle_complete_rate, 4),
            "required_doc_type_recall": round(required_doc_type_recall, 4),
            "selected_documents_total": selected_documents_total,
            "avg_selected_documents_per_active_deal": round(avg_selected_documents_per_active_deal, 4),
            "infra_failed": infra_failed,
            "total_api_calls": total_api_calls,
            "total_llm_gatekeeper_calls": total_llm_calls,
            "total_runtime_seconds": round(time.time() - self.start_time, 2),
            "deals_total": len(events_by_deal),
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
                f.write(json.dumps(e, ensure_ascii=False) + "\n")
        with open(self.report_path, "w", encoding="utf-8") as f:
            json.dump(report, f, indent=2)
