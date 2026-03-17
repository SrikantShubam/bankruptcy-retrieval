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


def _download_candidate(candidate: Dict[str, Any], deal_id: str) -> Tuple[bool, str]:
    download_url = candidate.get("resolved_pdf_url") or candidate.get("download_url") or candidate.get("absolute_url")
    if not isinstance(download_url, str) or not _is_allowed_download_url(download_url):
        return False, ""

    os.makedirs("downloads", exist_ok=True)
    out_path = os.path.join("downloads", f"{deal_id}.bin")
    req = Request(download_url, method="GET")
    try:
        with urlopen(req, timeout=20) as resp:
            content = resp.read(2 * 1024 * 1024)
        with open(out_path, "wb") as f:
            f.write(content)
        return True, out_path
    except (HTTPError, URLError, TimeoutError):
        return False, ""


def run_pipeline(deals: List[Dict[str, Any]], ground_truth: Dict[str, Dict[str, Any]]) -> Dict[str, Any]:
    planner = PlannerAgent()
    retriever = RetrieverAgent(max_calls_per_deal=8)
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
            plan = planner.build_plan(deal)
            candidates, api_calls = retriever.execute_plan(plan.variants, deal=deal)
            candidates, docket_verify_calls = retriever.verify_candidates_with_dockets(candidates, deal=deal, max_extra_calls=2)
            total_api_calls += api_calls + docket_verify_calls

            if not candidates:
                telemetry.record_terminal(
                    {
                        "deal_id": deal_id,
                        "pipeline_status": "NOT_FOUND",
                        "api_calls": api_calls + docket_verify_calls,
                        "runtime_seconds": time.time() - deal_start,
                        "downloaded_path": "",
                        "docket_verification_calls": docket_verify_calls,
                    }
                )
                continue

            chosen = None
            chosen_verification = None
            for candidate in candidates[:6]:
                verification = verifier.verify(deal, candidate)
                decision = decider.decide(deal, verification, candidate)
                if decision.get("used_llm"):
                    total_llm_calls += 1

                if decision.get("decision") == "DOWNLOAD" and verification.get("passed"):
                    chosen = candidate
                    chosen_verification = verification
                    break

            if not chosen:
                telemetry.record_terminal(
                    {
                        "deal_id": deal_id,
                        "pipeline_status": "SKIPPED",
                        "api_calls": api_calls + docket_verify_calls,
                        "runtime_seconds": time.time() - deal_start,
                        "downloaded_path": "",
                        "docket_verification_calls": docket_verify_calls,
                        "top_candidate_descriptions": [c.get("description", "")[:160] for c in candidates[:3]],
                    }
                )
                continue

            ok, path = _download_candidate(chosen, deal_id)
            telemetry.record_terminal(
                {
                    "deal_id": deal_id,
                    "pipeline_status": "DOWNLOADED" if ok else "FETCH_FAILED",
                    "api_calls": api_calls + docket_verify_calls,
                    "runtime_seconds": time.time() - deal_start,
                    "downloaded_path": path,
                    "docket_verification_calls": docket_verify_calls,
                    "selected_description": chosen.get("description", "")[:200],
                    "selected_score": chosen_verification.get("raw_score") if chosen_verification else None,
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
