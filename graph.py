import json
import os
import time
from typing import Any, Dict, List, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

from agents.decision import DecisionAgent
from agents.planner import PlannerAgent
from agents.retriever import InfraError, RetrieverAgent
from agents.verifier import VerifierAgent
from shared.config import DOWNLOAD_DIR, MAX_PDF_BYTES
from shared.telemetry import TelemetryCollector


ALLOWED_DOWNLOAD_HOSTS = ("courtlistener.com", "storage.courtlistener.com")


def _is_allowed_download_url(url: str) -> bool:
    if not url.startswith("https://"):
        return False
    return any(host in url for host in ALLOWED_DOWNLOAD_HOSTS)


def _preflight_courtlistener(token: str) -> Tuple[bool, str]:
    headers = {"Accept": "application/json"}
    if token:
        headers["Authorization"] = f"Token {token}"
    url = "https://www.courtlistener.com/api/rest/v4/search/?q=test&type=rd&page_size=1"
    req = Request(url, headers=headers, method="GET")
    try:
        with urlopen(req, timeout=10) as resp:
            if resp.status == 200:
                return True, "ok"
            return False, f"http_{resp.status}"
    except Exception as exc:
        return False, str(exc)


def _infer_doc_type(text: str) -> str:
    normalized = _normalize_doc_type(text)
    labels = {
        "credit_agreement": "Credit Agreement",
        "dip_motion": "DIP Motion",
        "first_day_declaration": "First Day Declaration",
        "cash_collateral_motion": "Cash Collateral Motion",
        "interim_dip_order": "Interim DIP Order",
        "sale_motion": "Sale Motion",
        "other_supporting": "Other Supporting",
    }
    return labels.get(normalized, "")


def _normalize_doc_type(text: str) -> str:
    value = (text or "").lower()
    if not value:
        return ""
    if "credit agreement" in value:
        return "credit_agreement"
    if any(token in value for token in ("debtor in possession financing", "dip motion", "postpetition financing", "dip financing")):
        return "dip_motion"
    if "cash collateral" in value:
        return "cash_collateral_motion"
    if "interim" in value and "dip" in value and "order" in value:
        return "interim_dip_order"
    if "sale motion" in value:
        return "sale_motion"
    if ("declaration" in value or "affidavit" in value) and (
        "first day" in value or "first-day" in value or "chapter 11 petitions" in value or "first day pleadings" in value or "first day papers" in value
    ):
        return "first_day_declaration"
    if value in {"dip_motion", "first_day_declaration", "cash_collateral_motion", "credit_agreement"}:
        return value
    return "other_supporting"


def _required_doc_types_for_deal(deal: Dict[str, Any], truth: Dict[str, Any]) -> List[str]:
    required: List[str] = []
    raw_required = truth.get("required_doc_types") or deal.get("required_doc_types") or []
    if isinstance(raw_required, list):
        for value in raw_required:
            normalized = _normalize_doc_type(str(value))
            if normalized and normalized not in required:
                required.append(normalized)
    if not required:
        for value in deal.get("target_doc_types", []) or []:
            normalized = _normalize_doc_type(str(value))
            if normalized and normalized not in required:
                required.append(normalized)
    if not required:
        for value in (truth.get("expected_best_source_doc_type"), truth.get("expected_doc_type"), deal.get("best_source_doc_type")):
            normalized = _normalize_doc_type(str(value or ""))
            if normalized and normalized not in required:
                required.append(normalized)
                break
    return required


DOC_TYPE_PRIORITY = [
    "credit_agreement",
    "dip_motion",
    "first_day_declaration",
    "cash_collateral_motion",
    "interim_dip_order",
    "sale_motion",
    "other_supporting",
]

MERGED_CANDIDATE_CAP = 30
CLASSIFY_CANDIDATE_CAP = 24
BUNDLE_CANDIDATE_CAP = 24


def _merge_candidates(existing: List[Dict[str, Any]], new_candidates: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    merged: List[Dict[str, Any]] = []
    seen_urls = set()
    for candidate in existing + new_candidates:
        url = str(candidate.get("resolved_pdf_url") or candidate.get("download_url") or candidate.get("absolute_url") or "")
        key = url or str(candidate.get("id") or "")
        if not key or key in seen_urls:
            continue
        seen_urls.add(key)
        merged.append(candidate)
    merged.sort(key=lambda c: float(c.get("score", 0.0) or 0.0), reverse=True)
    return merged[:MERGED_CANDIDATE_CAP]


def _classify_candidates(
    deal: Dict[str, Any],
    candidates: List[Dict[str, Any]],
    verifier: VerifierAgent,
    decider: DecisionAgent,
) -> Tuple[List[Dict[str, Any]], List[Dict[str, Any]], int]:
    approved_candidates: List[Dict[str, Any]] = []
    coverage_candidates: List[Dict[str, Any]] = []
    llm_calls = 0

    for candidate in candidates[:CLASSIFY_CANDIDATE_CAP]:
        verification = verifier.verify(deal, candidate)
        decision = decider.decide(deal, verification, candidate)
        if decision.get("used_llm"):
            llm_calls += 1

        normalized_doc_type = _normalize_doc_type(candidate.get("description", ""))
        candidate_with_verification = {
            **candidate,
            "normalized_doc_type": normalized_doc_type,
            "same_case_confirmed": bool(verification.get("same_case_confirmed")),
            "same_case_confidence": float(verification.get("same_case_confidence", 0.0) or 0.0),
            "provenance_status": verification.get("provenance_status", ""),
            "provenance_reason": verification.get("provenance_reason", ""),
        }

        if candidate_with_verification["same_case_confirmed"]:
            coverage_candidates.append(
                {
                    **candidate_with_verification,
                    "bundle_score": float(verification.get("score", 0.0) or 0.0)
                    + float(candidate.get("score", 0.0) or 0.0) / 10.0,
                    "selection_reason": "same_case_confirmed_candidate",
                }
            )

        if decision.get("decision") == "DOWNLOAD" and verification.get("passed"):
            approved_candidates.append(
                {
                    **candidate_with_verification,
                    "bundle_score": float(decision.get("confidence", 0.0) or 0.0)
                    + float(candidate.get("score", 0.0) or 0.0) / 10.0,
                    "selection_reason": "gatekeeper_download",
                }
            )

    return approved_candidates, coverage_candidates, llm_calls


def _select_bundle_candidates(approved_candidates: List[Dict[str, Any]], required_doc_types: List[str], bundle_cap: int = 4) -> List[Dict[str, Any]]:
    if not approved_candidates:
        return []

    seen_urls = set()
    deduped: List[Dict[str, Any]] = []
    for candidate in approved_candidates:
        if not candidate.get("same_case_confirmed", True):
            continue
        url = str(candidate.get("resolved_pdf_url") or candidate.get("download_url") or "").strip()
        if not url or url in seen_urls:
            continue
        seen_urls.add(url)
        deduped.append(candidate)

    ranked = sorted(
        deduped,
        key=lambda c: float(c.get("bundle_score", c.get("score", 0.0) or 0.0)),
        reverse=True,
    )

    best_by_type: Dict[str, Dict[str, Any]] = {}
    for candidate in ranked:
        doc_type = str(candidate.get("normalized_doc_type") or "")
        if not doc_type:
            continue
        if doc_type not in best_by_type:
            best_by_type[doc_type] = candidate

    selected: List[Dict[str, Any]] = []
    used_urls = set()

    for doc_type in required_doc_types:
        candidate = best_by_type.get(doc_type)
        if not candidate:
            continue
        url = str(candidate.get("resolved_pdf_url") or candidate.get("download_url") or "")
        if url in used_urls:
            continue
        selected.append({**candidate, "selection_reason": "required_coverage"})
        used_urls.add(url)
        if len(selected) >= bundle_cap:
            return selected

    for doc_type in DOC_TYPE_PRIORITY:
        candidate = best_by_type.get(doc_type)
        if not candidate:
            continue
        url = str(candidate.get("resolved_pdf_url") or candidate.get("download_url") or "")
        if url in used_urls:
            continue
        reason = "supporting_coverage" if doc_type not in required_doc_types else "required_coverage"
        selected.append({**candidate, "selection_reason": reason})
        used_urls.add(url)
        if len(selected) >= bundle_cap:
            return selected

    return selected[:bundle_cap]


def _safe_filename(value: str) -> str:
    keep = []
    for ch in value.lower():
        if ch.isalnum() or ch in ("_", "-", "."):
            keep.append(ch)
        elif ch in (" ", "/"):
            keep.append("_")
    normalized = "".join(keep).strip("._")
    return normalized or "document"


def _download_candidate(candidate: Dict[str, Any], deal_id: str, rank: int, normalized_doc_type: str) -> Tuple[bool, str]:
    download_url = candidate.get("resolved_pdf_url") or candidate.get("download_url") or candidate.get("absolute_url")
    if not isinstance(download_url, str) or not _is_allowed_download_url(download_url):
        return False, ""

    out_dir = os.path.join(DOWNLOAD_DIR, deal_id)
    os.makedirs(out_dir, exist_ok=True)
    file_name = f"{rank:02d}_{_safe_filename(normalized_doc_type)}.pdf"
    out_path = os.path.join(out_dir, file_name)
    req = Request(download_url, method="GET")
    try:
        with urlopen(req, timeout=20) as resp:
            chunks: List[bytes] = []
            bytes_read = 0
            while True:
                chunk = resp.read(8192)
                if not chunk:
                    break
                bytes_read += len(chunk)
                if bytes_read > MAX_PDF_BYTES:
                    return False, ""
                chunks.append(chunk)
        with open(out_path, "wb") as f:
            for chunk in chunks:
                f.write(chunk)
        return True, out_path
    except (HTTPError, URLError, TimeoutError):
        return False, ""


def _write_manifest(
    deal_id: str,
    selected_documents: List[Dict[str, Any]],
    required_doc_types: List[str],
    minimum_required_coverage: int,
) -> None:
    out_dir = os.path.join(DOWNLOAD_DIR, deal_id)
    os.makedirs(out_dir, exist_ok=True)
    selected_types = {str(d.get("normalized_doc_type") or "") for d in selected_documents}
    required_hits = [doc_type for doc_type in required_doc_types if doc_type in selected_types]
    manifest = {
        "deal_id": deal_id,
        "retrieval_mode": "coverage_bundle_v1",
        "bundle_cap": 4,
        "required_doc_types": required_doc_types,
        "minimum_required_coverage": minimum_required_coverage,
        "required_hits": required_hits,
        "bundle_complete": len(required_hits) >= minimum_required_coverage if required_doc_types else bool(selected_documents),
        "documents": selected_documents,
    }
    with open(os.path.join(out_dir, "manifest.json"), "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2)


def run_pipeline(deals: List[Dict[str, Any]], ground_truth: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    planner = PlannerAgent()
    retriever = RetrieverAgent(max_calls_per_deal=18)
    verifier = VerifierAgent()
    decider = DecisionAgent()
    telemetry = TelemetryCollector()

    total_api_calls = 0
    total_llm_calls = 0

    preflight_ok, preflight_detail = _preflight_courtlistener(os.getenv("COURTLISTENER_API_TOKEN", "").strip())

    for deal in deals:
        deal_id = str(deal.get("deal_id", "unknown-deal"))
        deal_start = time.time()

        if deal.get("already_processed"):
            telemetry.record_terminal(
                {
                    "deal_id": deal_id,
                    "pipeline_status": "ALREADY_PROCESSED",
                    "api_calls": 0,
                    "runtime_seconds": time.time() - deal_start,
                    "downloaded_path": "",
                    "docket_verification_calls": 0,
                }
            )
            continue

        if not preflight_ok:
            telemetry.record_terminal(
                {
                    "deal_id": deal_id,
                    "pipeline_status": "INFRA_FAILED",
                    "api_calls": 0,
                    "runtime_seconds": time.time() - deal_start,
                    "downloaded_path": "",
                    "infra_detail": preflight_detail,
                    "docket_verification_calls": 0,
                }
            )
            continue

        try:
            truth = ground_truth.get(deal_id, {})
            required_doc_types = _required_doc_types_for_deal(deal, truth)
            plan = planner.build_plan(deal)
            candidates, api_calls = retriever.execute_plan(plan.variants, deal=deal)
            candidates, docket_verify_calls = retriever.verify_candidates_with_dockets(candidates, deal=deal, max_extra_calls=4)
            total_api_calls += api_calls + docket_verify_calls

            # Docket fallback #1: if initial search returned nothing, try docket-first path
            if not candidates:
                docket_candidates, docket_api_calls = retriever.execute_docket_plan(deal)
                total_api_calls += docket_api_calls
                api_calls += docket_api_calls
                if docket_candidates:
                    candidates = _merge_candidates(candidates, docket_candidates)

            if not candidates:
                telemetry.record_terminal(
                    {
                        "deal_id": deal_id,
                        "pipeline_status": "NOT_FOUND",
                        "api_calls": api_calls + docket_verify_calls,
                        "runtime_seconds": time.time() - deal_start,
                        "downloaded_path": "",
                        "selected_documents": [],
                        "required_doc_types": required_doc_types,
                        "docket_verification_calls": docket_verify_calls,
                    }
                )
                continue

            approved_candidates, coverage_candidates, llm_calls = _classify_candidates(
                deal=deal,
                candidates=candidates,
                verifier=verifier,
                decider=decider,
            )
            total_llm_calls += llm_calls

            confirmed_same_case_candidates = [
                c for c in coverage_candidates if c.get("same_case_confirmed", False)
            ]

            if len(confirmed_same_case_candidates) <= 1:
                docket_variants = planner.build_docket_variants(deal)
                docket_candidates, docket_api_calls = retriever.execute_docket_plan(deal, docket_variants=docket_variants)
                total_api_calls += docket_api_calls
                api_calls += docket_api_calls
                if docket_candidates:
                    candidates = _merge_candidates(candidates, docket_candidates)
                    approved_candidates, coverage_candidates, docket_llm_calls = _classify_candidates(
                        deal=deal,
                        candidates=candidates,
                        verifier=verifier,
                        decider=decider,
                    )
                    total_llm_calls += docket_llm_calls

            confirmed_types = {
                str(c.get("normalized_doc_type") or "")
                for c in coverage_candidates
                if c.get("same_case_confirmed", False)
            }
            missing_required_doc_types = [doc_type for doc_type in required_doc_types if doc_type not in confirmed_types]
            if missing_required_doc_types:
                followup_variants = planner.build_followup_variants(deal, missing_required_doc_types)
                if followup_variants:
                    followup_candidates, followup_api_calls = retriever.execute_plan(followup_variants, deal=deal)
                    followup_candidates, followup_docket_calls = retriever.verify_candidates_with_dockets(
                        followup_candidates,
                        deal=deal,
                        max_extra_calls=4,
                    )
                    total_api_calls += followup_api_calls + followup_docket_calls
                    docket_verify_calls += followup_docket_calls
                    candidates = _merge_candidates(candidates, followup_candidates)
                    approved_candidates, coverage_candidates, followup_llm_calls = _classify_candidates(
                        deal=deal,
                        candidates=candidates,
                        verifier=verifier,
                        decider=decider,
                    )
                    total_llm_calls += followup_llm_calls

                    confirmed_same_case_candidates = [
                        c for c in coverage_candidates if c.get("same_case_confirmed", False)
                    ]
                    if len(confirmed_same_case_candidates) <= 1:
                        docket_variants = planner.build_docket_variants(deal)
                        docket_candidates, docket_api_calls = retriever.execute_docket_plan(deal, docket_variants=docket_variants)
                        total_api_calls += docket_api_calls
                        api_calls += docket_api_calls
                        if docket_candidates:
                            candidates = _merge_candidates(candidates, docket_candidates)
                            approved_candidates, coverage_candidates, docket_llm_calls = _classify_candidates(
                                deal=deal,
                                candidates=candidates,
                                verifier=verifier,
                                decider=decider,
                            )
                            total_llm_calls += docket_llm_calls

            # Docket fallback #2: if we still have no approved candidates, try docket path
            if not approved_candidates and not coverage_candidates:
                docket_variants = planner.build_docket_variants(deal)
                docket_candidates, docket_api_calls = retriever.execute_docket_plan(deal, docket_variants=docket_variants)
                total_api_calls += docket_api_calls
                api_calls += docket_api_calls
                if docket_candidates:
                    candidates = _merge_candidates(candidates, docket_candidates)
                    approved_candidates, coverage_candidates, docket_llm_calls = _classify_candidates(
                        deal=deal,
                        candidates=candidates,
                        verifier=verifier,
                        decider=decider,
                    )
                    total_llm_calls += docket_llm_calls

            if required_doc_types:
                selected_types = {str(c.get("normalized_doc_type") or "") for c in approved_candidates}
                selected_urls = {
                    str(c.get("resolved_pdf_url") or c.get("download_url") or "")
                    for c in approved_candidates
                }
                ranked_candidates = sorted(
                    coverage_candidates,
                    key=lambda c: float(c.get("score", 0.0) or 0.0),
                    reverse=True,
                )
                for required_doc_type in required_doc_types:
                    if required_doc_type in selected_types:
                        continue
                    for candidate in ranked_candidates:
                        normalized_doc_type = _normalize_doc_type(candidate.get("description", ""))
                        candidate_url = str(candidate.get("resolved_pdf_url") or candidate.get("download_url") or "")
                        if normalized_doc_type != required_doc_type:
                            continue
                        if not candidate_url or candidate_url in selected_urls:
                            continue
                        if not candidate.get("same_case_confirmed", False):
                            continue
                        approved_candidates.append(
                            {
                                **candidate,
                                "normalized_doc_type": normalized_doc_type,
                                "bundle_score": float(candidate.get("score", 0.0) or 0.0) / 10.0,
                                "selection_reason": "coverage_backfill_from_ranked_candidates",
                            }
                        )
                        selected_types.add(normalized_doc_type)
                        selected_urls.add(candidate_url)
                        break

            if not approved_candidates:
                telemetry.record_terminal(
                    {
                        "deal_id": deal_id,
                        "pipeline_status": "SKIPPED",
                        "api_calls": api_calls + docket_verify_calls,
                        "runtime_seconds": time.time() - deal_start,
                        "downloaded_path": "",
                        "selected_documents": [],
                        "required_doc_types": required_doc_types,
                        "docket_verification_calls": docket_verify_calls,
                        "top_candidate_descriptions": [c.get("description", "")[:160] for c in candidates[:3]],
                    }
                )
                continue

            minimum_required = truth.get("minimum_required_coverage")
            if not isinstance(minimum_required, int) or minimum_required <= 0:
                minimum_required = len(required_doc_types) if required_doc_types else 1

            bundle_candidates = _select_bundle_candidates(
                approved_candidates=sorted(
                    approved_candidates,
                    key=lambda c: float(c.get("bundle_score", c.get("score", 0.0) or 0.0)),
                    reverse=True,
                )[:BUNDLE_CANDIDATE_CAP],
                required_doc_types=required_doc_types,
                bundle_cap=4,
            )

            selected_documents: List[Dict[str, Any]] = []
            downloaded_paths: List[str] = []
            for rank, candidate in enumerate(bundle_candidates, start=1):
                normalized_doc_type = str(candidate.get("normalized_doc_type") or "")
                if not normalized_doc_type:
                    normalized_doc_type = _normalize_doc_type(candidate.get("description", ""))
                if not normalized_doc_type:
                    normalized_doc_type = "other_supporting"
                ok, path = _download_candidate(candidate, deal_id, rank, normalized_doc_type)
                if not ok:
                    continue
                downloaded_paths.append(path)
                selected_documents.append(
                    {
                        "rank": rank,
                        "normalized_doc_type": normalized_doc_type,
                        "local_path": path,
                        "source_url": candidate.get("resolved_pdf_url") or candidate.get("download_url") or "",
                        "candidate_title": candidate.get("description", ""),
                        "source_system": "courtlistener",
                        "selection_reason": candidate.get("selection_reason", "ranked_bundle"),
                        "engine_relevant": normalized_doc_type != "other_supporting",
                        "same_case_confirmed": bool(candidate.get("same_case_confirmed", False)),
                        "provenance_status": candidate.get("provenance_status", ""),
                        "provenance_reason": candidate.get("provenance_reason", ""),
                    }
                )

            _write_manifest(
                deal_id=deal_id,
                selected_documents=selected_documents,
                required_doc_types=required_doc_types,
                minimum_required_coverage=minimum_required,
            )

            telemetry.record_terminal(
                {
                    "deal_id": deal_id,
                    "pipeline_status": "DOWNLOADED" if selected_documents else "FETCH_FAILED",
                    "api_calls": api_calls + docket_verify_calls,
                    "runtime_seconds": time.time() - deal_start,
                    "downloaded_path": downloaded_paths[0] if downloaded_paths else "",
                    "downloaded_paths": downloaded_paths,
                    "selected_documents": selected_documents,
                    "required_doc_types": required_doc_types,
                    "docket_verification_calls": docket_verify_calls,
                    "selected_description": selected_documents[0].get("candidate_title", "")[:200] if selected_documents else "",
                    "selected_doc_type": _infer_doc_type(selected_documents[0].get("normalized_doc_type", "")) if selected_documents else "",
                    "selected_doc_types": [d.get("normalized_doc_type", "") for d in selected_documents],
                }
            )
        except InfraError as exc:
            telemetry.record_terminal(
                {
                    "deal_id": deal_id,
                    "pipeline_status": "INFRA_FAILED",
                    "api_calls": 0,
                    "runtime_seconds": time.time() - deal_start,
                    "downloaded_path": "",
                    "infra_detail": str(exc),
                    "docket_verification_calls": 0,
                }
            )

    report = telemetry.summarize(ground_truth=ground_truth, total_api_calls=total_api_calls, total_llm_calls=total_llm_calls)
    telemetry.flush(report)
    return report


def load_json(path: str, default: Any) -> Any:
    if not os.path.exists(path):
        return default
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)
