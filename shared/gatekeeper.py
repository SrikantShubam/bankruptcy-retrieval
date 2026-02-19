"""
shared/gatekeeper.py
─────────────────────────────────────────────────────────────────────────────
LLM Gatekeeper — evaluates docket metadata and decides DOWNLOAD vs SKIP.

Rules this module enforces:
  • Never receives PDF bytes or full PDF text — metadata only
  • Calls Llama 3.1 8B via NVIDIA NIM or OpenRouter (configurable via .env)
  • Returns a structured GatekeeperResult with score, verdict, reasoning
  • Temperature is always 0.0 for deterministic output
  • Max 150 tokens per response
  • Verdict threshold: score >= GATEKEEPER_SCORE_THRESHOLD → DOWNLOAD

Used identically by all three worktrees.
─────────────────────────────────────────────────────────────────────────────
"""

from __future__ import annotations

import json
import time
import logging
from dataclasses import dataclass, field
from typing import Literal

import httpx

# Import shared config (also loads .env)
from shared.config import (
    GATEKEEPER_PROVIDER,
    GATEKEEPER_MODEL_NIM,
    GATEKEEPER_MODEL_OR,
    GATEKEEPER_SCORE_THRESHOLD,
    NVIDIA_NIM_API_KEY,
    OPENROUTER_API_KEY,
)

logger = logging.getLogger(__name__)


# ─────────────────────────────────────────────────────────────────────────────
# Data Contracts
# ─────────────────────────────────────────────────────────────────────────────

@dataclass
class CandidateDocument:
    """
    The ONLY input the Gatekeeper ever receives.
    No PDF bytes. No full OCR text. Metadata only.
    """
    deal_id: str
    source: str                          # "courtlistener" | "kroll" | "stretto" | "epiq"
    docket_entry_id: str
    docket_title: str                    # Raw title from docket entry
    filing_date: str                     # YYYY-MM-DD
    attachment_descriptions: list[str]   # Max 5 entries — descriptions only, no content
    resolved_pdf_url: str | None = None
    api_calls_consumed: int = 0


@dataclass
class GatekeeperResult:
    """
    Output from a single Gatekeeper evaluation.
    """
    verdict: Literal["DOWNLOAD", "SKIP"]
    score: float                    # 0.0 – 1.0
    reasoning: str                  # One sentence, max 200 chars
    token_count: int = 0
    model_used: str = ""
    latency_ms: int = 0
    error: str | None = None        # Set if the LLM call failed; verdict defaults to SKIP


# ─────────────────────────────────────────────────────────────────────────────
# Prompt Template
# ─────────────────────────────────────────────────────────────────────────────

_SYSTEM_PROMPT = """\
You are a financial document classifier specialising in Chapter 11 bankruptcy cases.
Your job is to decide whether a docket entry likely contains substantive capital
structure or debt financing information.

Documents that QUALIFY (score 0.70–1.0, verdict DOWNLOAD):
- First Day Declarations or Declarations in Support of First Day Motions
- DIP (Debtor-in-Possession) financing motions
- Cash collateral motions with capital structure narrative
- Motions explicitly referencing prepetition debt, credit agreements, or loan facilities
- Documents titled "Declaration of [Name] in Support of..." related to financing

Documents that DO NOT QUALIFY (score 0.0–0.50, verdict SKIP):
- Fee applications, retention applications, professional fee statements
- Service affidavits, proof of service, certificates of service
- Scheduling orders, case management orders, procedural motions
- Schedules of assets and liabilities without narrative debt description
- Sale motions without explicit capital structure context
- Any document from a company with no plausible Chapter 11 filing

CRITICAL RULES:
1. Base your decision ONLY on the docket title and attachment descriptions provided.
2. You have NOT read the PDF. Do not invent or assume PDF content.
3. Respond with valid JSON only. No preamble. No explanation outside the JSON.
4. Your reasoning must be one sentence and must NOT reference any PDF content.
"""

_USER_PROMPT_TEMPLATE = """\
Evaluate this docket entry:

Filing date: {filing_date}
Docket title: {docket_title}
Attachment descriptions: {attachment_descriptions}

Respond with this exact JSON structure:
{{
  "score": <float 0.0 to 1.0>,
  "verdict": "<DOWNLOAD or SKIP>",
  "reasoning": "<one sentence, max 200 characters, based only on title and descriptions>"
}}
"""


# ─────────────────────────────────────────────────────────────────────────────
# API Endpoints
# ─────────────────────────────────────────────────────────────────────────────

_NVIDIA_NIM_URL  = "https://integrate.api.nvidia.com/v1/chat/completions"
_OPENROUTER_URL  = "https://openrouter.ai/api/v1/chat/completions"


# ─────────────────────────────────────────────────────────────────────────────
# LLMGatekeeper Class
# ─────────────────────────────────────────────────────────────────────────────

class LLMGatekeeper:
    """
    Evaluates a CandidateDocument using a lightweight LLM.
    Instantiate once per pipeline run; reuse across all deals.

    Example:
        gatekeeper = LLMGatekeeper()
        result = await gatekeeper.evaluate(candidate)
        if result.verdict == "DOWNLOAD":
            ...
    """

    def __init__(
        self,
        provider: str | None = None,
        score_threshold: float | None = None,
    ):
        self.provider         = (provider or GATEKEEPER_PROVIDER).lower()
        self.score_threshold  = score_threshold if score_threshold is not None \
                                else GATEKEEPER_SCORE_THRESHOLD

        if self.provider == "nvidia_nim":
            self.api_url   = _NVIDIA_NIM_URL
            self.api_key   = NVIDIA_NIM_API_KEY
            self.model     = GATEKEEPER_MODEL_NIM
        else:
            # Default: OpenRouter
            self.provider  = "openrouter"
            self.api_url   = _OPENROUTER_URL
            self.api_key   = OPENROUTER_API_KEY
            self.model     = GATEKEEPER_MODEL_OR

        if not self.api_key:
            raise ValueError(
                f"[LLMGatekeeper] No API key found for provider '{self.provider}'. "
                f"Check your .env file."
            )

    # ──────────────────────────────────────────────────────────────────────
    # Public interface
    # ──────────────────────────────────────────────────────────────────────

    async def evaluate(self, candidate: CandidateDocument) -> GatekeeperResult:
        """
        Evaluate a CandidateDocument.  Returns GatekeeperResult.
        On any LLM error, returns a SKIP result with error field set —
        the pipeline should treat this as a conservative rejection.
        """
        user_content = _USER_PROMPT_TEMPLATE.format(
            filing_date=candidate.filing_date,
            docket_title=candidate.docket_title,
            attachment_descriptions="; ".join(
                candidate.attachment_descriptions[:5]
            ) or "None provided",
        )

        payload = {
            "model":       self.model,
            "temperature": 0.0,
            "max_tokens":  150,
            "messages": [
                {"role": "system", "content": _SYSTEM_PROMPT},
                {"role": "user",   "content": user_content},
            ],
        }

        headers = {
            "Content-Type":  "application/json",
            "Authorization": f"Bearer {self.api_key}",
        }
        # OpenRouter requires extra headers for attribution
        if self.provider == "openrouter":
            headers["HTTP-Referer"] = "https://github.com/bankruptcy-retrieval"
            headers["X-Title"]      = "Bankruptcy Document Retrieval"

        t0 = time.monotonic()
        try:
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(
                    self.api_url, json=payload, headers=headers
                )
                response.raise_for_status()
                data = response.json()

            latency_ms  = int((time.monotonic() - t0) * 1000)
            raw_text    = data["choices"][0]["message"]["content"].strip()
            token_count = data.get("usage", {}).get("total_tokens", 0)

            return self._parse_response(
                raw_text, token_count, latency_ms
            )

        except httpx.HTTPStatusError as exc:
            logger.warning(
                "[LLMGatekeeper] HTTP %s for deal %s: %s",
                exc.response.status_code, candidate.deal_id, exc.response.text[:200],
            )
            return GatekeeperResult(
                verdict="SKIP", score=0.0,
                reasoning="LLM call failed — HTTP error",
                error=f"HTTP {exc.response.status_code}",
                latency_ms=int((time.monotonic() - t0) * 1000),
                model_used=self.model,
            )

        except Exception as exc:
            logger.warning(
                "[LLMGatekeeper] Unexpected error for deal %s: %s",
                candidate.deal_id, exc,
            )
            return GatekeeperResult(
                verdict="SKIP", score=0.0,
                reasoning="LLM call failed — unexpected error",
                error=str(exc),
                latency_ms=int((time.monotonic() - t0) * 1000),
                model_used=self.model,
            )

    # ──────────────────────────────────────────────────────────────────────
    # Synchronous wrapper (for non-async contexts)
    # ──────────────────────────────────────────────────────────────────────

    def evaluate_sync(self, candidate: CandidateDocument) -> GatekeeperResult:
        """Blocking wrapper around evaluate().  Use only in non-async contexts."""
        import asyncio
        return asyncio.run(self.evaluate(candidate))

    # ──────────────────────────────────────────────────────────────────────
    # Internal helpers
    # ──────────────────────────────────────────────────────────────────────

    def _parse_response(
        self,
        raw_text: str,
        token_count: int,
        latency_ms: int,
    ) -> GatekeeperResult:
        """
        Parse the LLM's raw JSON response into a GatekeeperResult.
        Handles common malformations: markdown fences, trailing commas, etc.
        Falls back to SKIP on any parse failure.
        """
        # Strip markdown code fences if the model wrapped its response
        cleaned = raw_text
        if cleaned.startswith("```"):
            lines = cleaned.splitlines()
            cleaned = "\n".join(
                line for line in lines
                if not line.strip().startswith("```")
            ).strip()

        try:
            parsed = json.loads(cleaned)
        except json.JSONDecodeError:
            # Last-ditch attempt: find the first {...} block
            import re
            match = re.search(r'\{[^}]+\}', cleaned, re.DOTALL)
            if match:
                try:
                    parsed = json.loads(match.group())
                except json.JSONDecodeError:
                    return self._fallback_skip(
                        f"JSON parse failed: {raw_text[:120]}", token_count, latency_ms
                    )
            else:
                return self._fallback_skip(
                    f"No JSON found in response: {raw_text[:120]}", token_count, latency_ms
                )

        # Validate and extract fields
        try:
            score   = float(parsed.get("score", 0.0))
            score   = max(0.0, min(1.0, score))   # clamp to [0, 1]
            reasoning = str(parsed.get("reasoning", "No reasoning provided"))[:200]
            # Derive verdict from score using threshold (don't blindly trust model's verdict)
            verdict: Literal["DOWNLOAD", "SKIP"] = (
                "DOWNLOAD" if score >= self.score_threshold else "SKIP"
            )
        except (TypeError, ValueError) as exc:
            return self._fallback_skip(str(exc), token_count, latency_ms)

        return GatekeeperResult(
            verdict=verdict,
            score=score,
            reasoning=reasoning,
            token_count=token_count,
            model_used=self.model,
            latency_ms=latency_ms,
        )

    def _fallback_skip(
        self, error_msg: str, token_count: int, latency_ms: int
    ) -> GatekeeperResult:
        logger.warning("[LLMGatekeeper] Falling back to SKIP: %s", error_msg)
        return GatekeeperResult(
            verdict="SKIP",
            score=0.0,
            reasoning="Parse failure — conservative SKIP",
            token_count=token_count,
            model_used=self.model,
            latency_ms=latency_ms,
            error=error_msg,
        )
