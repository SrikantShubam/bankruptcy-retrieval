import json
import os
from typing import Any, Dict, List, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


class InfraError(Exception):
    pass


class RetrieverAgent:
    """CourtListener retriever with bounded calls and strategy-changing retries."""

    BASE_URL = "https://www.courtlistener.com/api/rest/v4/search/"

    def __init__(self, max_calls_per_deal: int = 6, timeout_seconds: int = 20) -> None:
        self.token = os.getenv("COURTLISTENER_API_TOKEN", "").strip()
        self.max_calls_per_deal = max_calls_per_deal
        self.timeout_seconds = timeout_seconds

    def _get_json(self, url: str) -> Dict[str, Any]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Token {self.token}"

        req = Request(url, headers=headers, method="GET")
        try:
            with urlopen(req, timeout=self.timeout_seconds) as resp:
                payload = resp.read().decode("utf-8")
            data = json.loads(payload)
            if not isinstance(data, dict):
                raise InfraError("CourtListener response is not a JSON object")
            return data
        except (HTTPError, URLError, TimeoutError, ValueError) as exc:
            raise InfraError(str(exc)) from exc

    def _normalize_url(self, value: Any) -> str:
        s = str(value or "").strip()
        if not s:
            return ""
        if s.startswith("/"):
            return f"https://www.courtlistener.com{s}"
        if s.startswith("http://") or s.startswith("https://"):
            return s
        return ""

    def _normalize_candidate(self, item: Dict[str, Any], variant_name: str) -> Dict[str, Any]:
        absolute_url = self._normalize_url(item.get("absolute_url"))
        download_url = self._normalize_url(item.get("download_url") or item.get("download_url_original") or item.get("filepath_local"))

        return {
            "id": str(item.get("id", "")).strip(),
            "case_name": str(item.get("caseName") or item.get("case_name") or "").strip(),
            "docket_number": str(item.get("docketNumber") or item.get("docket_number") or "").strip(),
            "court": str(item.get("court") or item.get("court_id") or "").strip(),
            "absolute_url": absolute_url,
            "download_url": download_url,
            "_query_variant": variant_name,
            "_raw": item,
        }

    def execute_plan(self, plan_variants: List[Dict[str, Any]]) -> Tuple[List[Dict[str, Any]], int]:
        calls = 0
        all_candidates: List[Dict[str, Any]] = []
        seen_keys = set()

        for variant in plan_variants:
            if calls >= self.max_calls_per_deal:
                break

            query = {
                "q": variant.get("q", ""),
                "type": variant.get("type", "rd"),
                "page_size": 20,
            }
            url = f"{self.BASE_URL}?{urlencode(query)}"
            data = self._get_json(url)
            calls += 1

            results = data.get("results")
            if not isinstance(results, list):
                raise InfraError("CourtListener results payload missing list field")

            normalized_batch = []
            for item in results:
                if not isinstance(item, dict):
                    continue
                normalized = self._normalize_candidate(item, variant.get("name", "unknown"))
                dedupe_key = normalized["id"] or normalized["absolute_url"]
                if not dedupe_key or dedupe_key in seen_keys:
                    continue
                seen_keys.add(dedupe_key)
                normalized_batch.append(normalized)

            all_candidates.extend(normalized_batch)

            # Adaptive stopping: strict results found, stop early.
            if variant.get("name") == "strict_rd" and normalized_batch:
                break

        return all_candidates, calls
