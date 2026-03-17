import json
import os
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class DecisionAgent:
    """Decision agent using OpenRouter hunter-alpha with deterministic fallback."""

    URL = "https://openrouter.ai/api/v1/chat/completions"
    ALLOWED = {"DOWNLOAD", "SKIP", "RETRY_QUERY"}

    def __init__(self, timeout_seconds: int = 10) -> None:
        self.api_key = os.getenv("OPENROUTER_API_KEY", "").strip()
        self.timeout_seconds = timeout_seconds

    def _fallback(self, verification: Dict[str, Any]) -> Dict[str, Any]:
        return {
            "decision": "DOWNLOAD" if verification.get("passed") else "SKIP",
            "confidence": float(verification.get("score", 0.0) or 0.0),
            "used_llm": False,
        }

    def _normalize_decision(self, parsed: Dict[str, Any], verification: Dict[str, Any]) -> Dict[str, Any]:
        raw_decision = str(parsed.get("decision", "SKIP")).strip().upper()
        decision = raw_decision if raw_decision in self.ALLOWED else "SKIP"
        try:
            confidence = float(parsed.get("confidence", verification.get("score", 0.0) or 0.0))
        except (TypeError, ValueError):
            confidence = float(verification.get("score", 0.0) or 0.0)
        confidence = max(0.0, min(1.0, confidence))
        return {
            "decision": decision,
            "confidence": confidence,
            "used_llm": True,
        }

    def _llm_decide(self, deal: Dict[str, Any], verification: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_key:
            return self._fallback(verification)

        prompt = {
            "deal": {
                "deal_id": deal.get("deal_id"),
                "company_name": deal.get("company_name"),
                "court": deal.get("court"),
                "filing_year": deal.get("filing_year"),
            },
            "candidate": {
                "case_name": candidate.get("case_name"),
                "description": candidate.get("description"),
                "query_variant": candidate.get("_query_variant"),
            },
            "verification": verification,
            "policy": "Return JSON with decision in {DOWNLOAD,SKIP,RETRY_QUERY} and confidence in [0,1]. Prefer DOWNLOAD when candidate clearly looks like first-day declaration or DIP motion for the same company.",
        }

        body = {
            "model": "openrouter/hunter-alpha",
            "temperature": 0,
            "response_format": {"type": "json_object"},
            "messages": [
                {"role": "system", "content": "You are a strict legal retrieval gatekeeper."},
                {"role": "user", "content": json.dumps(prompt)},
            ],
        }

        req = Request(
            self.URL,
            headers={
                "Authorization": f"Bearer {self.api_key}",
                "Content-Type": "application/json",
            },
            data=json.dumps(body).encode("utf-8"),
            method="POST",
        )

        try:
            with urlopen(req, timeout=self.timeout_seconds) as resp:
                raw = json.loads(resp.read().decode("utf-8"))

            content = raw.get("choices", [{}])[0].get("message", {}).get("content", "{}")
            parsed = content if isinstance(content, dict) else json.loads(str(content))
            if not isinstance(parsed, dict):
                return self._fallback(verification)
            return self._normalize_decision(parsed, verification)
        except (KeyError, ValueError, TypeError, HTTPError, URLError, TimeoutError):
            return self._fallback(verification)

    def decide(self, deal: Dict[str, Any], verification: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
        score = float(verification.get("score", 0.0) or 0.0)

        # Deterministic fast path for clear positives/negatives.
        if verification.get("passed") and score >= 0.7:
            return {"decision": "DOWNLOAD", "confidence": score, "used_llm": False}
        if (not verification.get("passed")) and score <= 0.25:
            return {"decision": "SKIP", "confidence": score, "used_llm": False}

        return self._llm_decide(deal, verification, candidate)
