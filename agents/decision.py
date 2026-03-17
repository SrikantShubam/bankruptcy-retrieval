import json
import os
from typing import Any, Dict
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen


class DecisionAgent:
    """Decision agent using OpenRouter hunter-alpha with deterministic fallback."""

    URL = "https://openrouter.ai/api/v1/chat/completions"
    ALLOWED = {"DOWNLOAD", "SKIP", "RETRY_QUERY"}

    def __init__(self, timeout_seconds: int = 12) -> None:
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

    def _llm_decide(self, deal: Dict[str, Any], verification: Dict[str, Any]) -> Dict[str, Any]:
        if not self.api_key:
            return self._fallback(verification)

        prompt = {
            "deal": {
                "deal_id": deal.get("deal_id"),
                "company": deal.get("company"),
                "court": deal.get("court"),
            },
            "verification": verification,
            "policy": "Return JSON with decision in {DOWNLOAD,SKIP,RETRY_QUERY} and confidence in [0,1].",
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
            if isinstance(content, dict):
                parsed = content
            else:
                parsed = json.loads(str(content))
            if not isinstance(parsed, dict):
                return self._fallback(verification)
            return self._normalize_decision(parsed, verification)
        except (KeyError, ValueError, TypeError, HTTPError, URLError, TimeoutError):
            return self._fallback(verification)

    def decide(self, deal: Dict[str, Any], verification: Dict[str, Any]) -> Dict[str, Any]:
        return self._llm_decide(deal, verification)
