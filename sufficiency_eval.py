import argparse
import json
import os
from pathlib import Path
from typing import Any, Callable, Dict, List

import requests
from pypdf import PdfReader


V4_CRITICAL_FIELDS = [
    "total_leverage",
    "add_backs_percent",
    "covenant_lite",
    "largest_customer_percent",
]

DEFAULT_MODEL = os.environ.get("NVIDIA_MODEL", "meta/llama-3.3-70b-instruct")
DEFAULT_BASE_URL = os.environ.get("NVIDIA_API_BASE_URL", "https://integrate.api.nvidia.com/v1")
TARGETED_TERMS = (
    "total leverage",
    "net leverage",
    "ebitda",
    "adjusted ebitda",
    "add-backs",
    "add backs",
    "covenant",
    "largest customer",
    "customer concentration",
    "dip facility",
    "postpetition financing",
    "credit agreement",
    "cash collateral",
    "prepetition debt",
    "capital structure",
)


def load_dotenv(path: Path) -> None:
    if not path.exists():
        return
    for raw in path.read_text(encoding="utf-8").splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")
        if key and key not in os.environ:
            os.environ[key] = value


def load_known_env_sources(project_root: Path) -> None:
    load_dotenv(project_root / ".env")
    load_dotenv(project_root.parent / "ag dead deal autopsy" / "v4" / ".env")


def resolve_local_path(manifest_path: Path, local_path: str) -> Path:
    cleaned = local_path.replace("\\", os.sep).replace("/", os.sep)
    if cleaned.startswith(f".{os.sep}downloads{os.sep}"):
        project_root = manifest_path.parent.parent.parent
        return (project_root / cleaned[2:]).resolve()
    candidate = Path(cleaned)
    if candidate.is_absolute():
        return candidate
    return (manifest_path.parent / candidate).resolve()


def extract_pdf_text(pdf_path: Path, max_pages: int = 30, max_chars: int = 40000) -> str:
    reader = PdfReader(str(pdf_path))
    page_texts: List[str] = []
    for page in reader.pages[:max_pages]:
        text = page.extract_text() or ""
        text = " ".join(text.split())
        page_texts.append(text)

    prioritized_indexes: List[int] = []
    for idx, text in enumerate(page_texts):
        normalized = text.lower()
        if any(term in normalized for term in TARGETED_TERMS):
            prioritized_indexes.append(idx)

    selected_indexes: List[int] = []
    for idx in prioritized_indexes + list(range(len(page_texts))):
        if idx not in selected_indexes:
            selected_indexes.append(idx)

    parts: List[str] = []
    for idx in selected_indexes:
        text = page_texts[idx]
        if text:
            parts.append(f"[Page {idx + 1}] {text}")
        if sum(len(part) for part in parts) >= max_chars:
            break
    combined = "\n\n".join(parts)
    return combined[:max_chars]


def build_sufficiency_prompt(deal_id: str, manifest: Dict[str, Any], docs: List[Dict[str, Any]]) -> str:
    required_doc_types = manifest.get("required_doc_types") or []
    minimum_required_coverage = manifest.get("minimum_required_coverage")
    docs_block = []
    for index, doc in enumerate(docs, start=1):
        docs_block.append(
            "\n".join(
                [
                    f"Document {index}",
                    f"- normalized_doc_type: {doc.get('normalized_doc_type', '')}",
                    f"- same_case_confirmed: {doc.get('same_case_confirmed', False)}",
                    f"- title: {doc.get('candidate_title', '')}",
                    f"- extracted_text_excerpt: {doc.get('text_excerpt', '')}",
                ]
            )
        )

    return (
        "You are evaluating whether a bankruptcy document bundle is sufficient to power a financial extraction engine.\n"
        "Judge practical sufficiency, not benchmark purity.\n"
        f"Deal ID: {deal_id}\n"
        f"Critical fields: {', '.join(V4_CRITICAL_FIELDS)}\n"
        f"Required document types from retrieval benchmark: {required_doc_types}\n"
        f"Minimum required coverage target: {minimum_required_coverage}\n"
        "Allowed values for missing_doc_type: first_day_declaration, dip_motion, credit_agreement, cash_collateral_motion, other_supporting, unknown, null.\n"
        "Answer ONLY with JSON having these keys:\n"
        "{"
        '"sufficient_for_v4": boolean, '
        '"sufficient_for_critical_fields": boolean, '
        '"missing_doc_likely_exists": boolean, '
        '"missing_doc_type": string|null, '
        '"likely_missing_reason": string, '
        '"critical_fields_supported": string[], '
        '"critical_fields_blocked": string[], '
        '"verdict": string, '
        '"notes": string'
        "}\n"
        "Rules:\n"
        "- Say true for sufficient_for_v4 only if the bundle is enough for a reliable v4-style extraction of financing and capital-structure facts, not merely a weak first pass.\n"
        "- Say true for sufficient_for_critical_fields only if the critical fields above are mostly supportable from the bundle.\n"
        "- If fewer than two critical fields are reasonably supportable, sufficient_for_v4 should usually be false.\n"
        "- If a same-case financing or capital-structure document is obviously missing, sufficient_for_v4 should be false.\n"
        "- If another important source document likely exists but is missing, set missing_doc_likely_exists=true and name the most likely missing_doc_type.\n"
        "- Do not mention URLs or file locations.\n\n"
        "Documents:\n"
        + "\n\n".join(docs_block)
    )


def extract_json_object(raw: str) -> Dict[str, Any]:
    raw = raw.strip()
    if raw.startswith("```"):
        first = raw.find("{")
        last = raw.rfind("}")
        if first != -1 and last != -1 and last > first:
            raw = raw[first : last + 1]
    else:
        first = raw.find("{")
        last = raw.rfind("}")
        if first != -1 and last != -1 and last > first:
            raw = raw[first : last + 1]
    return json.loads(raw)


def call_nvidia_chat(prompt: str, api_key: str, model: str, base_url: str, timeout: int = 180) -> str:
    response = requests.post(
        f"{base_url.rstrip('/')}/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.1,
        },
        timeout=timeout,
    )
    response.raise_for_status()
    body = response.json()
    message = ((body.get("choices") or [{}])[0].get("message") or {}).get("content")
    if isinstance(message, list):
        message = "".join(part.get("text", "") for part in message if isinstance(part, dict))
    if not isinstance(message, str):
        raise ValueError(f"Unexpected response payload: {body}")
    return message


def evaluate_manifest(
    manifest_path: Path,
    api_key: str,
    model: str,
    base_url: str,
    llm_caller: Callable[[str, str, str, str, int], str] = call_nvidia_chat,
    text_extractor: Callable[[Path, int, int], str] = extract_pdf_text,
) -> Dict[str, Any]:
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    documents = manifest.get("documents") or []
    doc_payloads: List[Dict[str, Any]] = []
    for document in documents:
        local_path = document.get("local_path")
        if not local_path:
            continue
        resolved_path = resolve_local_path(manifest_path, str(local_path))
        text_excerpt = ""
        if resolved_path.exists():
            try:
                text_excerpt = text_extractor(resolved_path, 8, 12000)
            except Exception as exc:
                text_excerpt = f"[text extraction failed: {exc}]"
        else:
            text_excerpt = "[file missing]"
        doc_payloads.append(
            {
                "normalized_doc_type": document.get("normalized_doc_type"),
                "same_case_confirmed": bool(document.get("same_case_confirmed", False)),
                "candidate_title": document.get("candidate_title", ""),
                "text_excerpt": text_excerpt,
            }
        )

    prompt = build_sufficiency_prompt(
        deal_id=str(manifest.get("deal_id") or manifest_path.parent.name),
        manifest=manifest,
        docs=doc_payloads,
    )
    raw_response = llm_caller(prompt, api_key, model, base_url, 180)
    parsed = extract_json_object(raw_response)

    return {
        "deal_id": str(manifest.get("deal_id") or manifest_path.parent.name),
        "documents_reviewed": len(doc_payloads),
        "available_doc_types": [doc.get("normalized_doc_type") for doc in doc_payloads if doc.get("normalized_doc_type")],
        "sufficient_for_v4": bool(parsed.get("sufficient_for_v4", False)),
        "sufficient_for_critical_fields": bool(parsed.get("sufficient_for_critical_fields", False)),
        "missing_doc_likely_exists": bool(parsed.get("missing_doc_likely_exists", False)),
        "missing_doc_type": parsed.get("missing_doc_type"),
        "likely_missing_reason": parsed.get("likely_missing_reason", ""),
        "critical_fields_supported": parsed.get("critical_fields_supported") or [],
        "critical_fields_blocked": parsed.get("critical_fields_blocked") or [],
        "verdict": parsed.get("verdict", ""),
        "notes": parsed.get("notes", ""),
    }


def evaluate_download_dir(
    download_dir: Path,
    output_path: Path,
    api_key: str,
    model: str,
    base_url: str,
) -> Dict[str, Any]:
    manifest_paths = sorted(download_dir.rglob("manifest.json"))
    deals: List[Dict[str, Any]] = []
    for manifest_path in manifest_paths:
        deals.append(
            evaluate_manifest(
                manifest_path=manifest_path,
                api_key=api_key,
                model=model,
                base_url=base_url,
            )
        )

    sufficient_for_v4 = sum(1 for deal in deals if deal["sufficient_for_v4"])
    sufficient_for_critical_fields = sum(1 for deal in deals if deal["sufficient_for_critical_fields"])
    missing_doc_likely_exists = sum(1 for deal in deals if deal["missing_doc_likely_exists"])

    report = {
        "model": model,
        "deals_evaluated": len(deals),
        "sufficient_for_v4_count": sufficient_for_v4,
        "sufficient_for_critical_fields_count": sufficient_for_critical_fields,
        "missing_doc_likely_exists_count": missing_doc_likely_exists,
        "deals": deals,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(report, indent=2), encoding="utf-8")
    return report


def main() -> None:
    project_root = Path(__file__).parent
    load_known_env_sources(project_root)

    parser = argparse.ArgumentParser(description="Evaluate D download bundles for v4 sufficiency")
    parser.add_argument("--download-dir", default=str(project_root / "downloads"))
    parser.add_argument("--output", default=str(project_root / "logs" / "v4_sufficiency_report.json"))
    parser.add_argument("--model", default=os.environ.get("NVIDIA_MODEL", DEFAULT_MODEL))
    parser.add_argument("--base-url", default=os.environ.get("NVIDIA_API_BASE_URL", DEFAULT_BASE_URL))
    args = parser.parse_args()

    api_key = os.environ.get("NVIDIA_API_KEY", "")
    if not api_key:
        raise ValueError("NVIDIA_API_KEY is missing. Add it to .env or the environment.")

    report = evaluate_download_dir(
        download_dir=Path(args.download_dir),
        output_path=Path(args.output),
        api_key=api_key,
        model=args.model,
        base_url=args.base_url,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
