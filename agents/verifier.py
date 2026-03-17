from typing import Any, Dict


class VerifierAgent:
    """Deterministic verifier for company/court alignment and obvious reject rules."""

    def verify(self, deal: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
        company = (deal.get("company_name") or deal.get("company") or "").lower()
        court = (deal.get("court") or "").lower()

        haystack = " ".join(
            [
                str(candidate.get("caseName", "")),
                str(candidate.get("case_name", "")),
                str(candidate.get("docket_number", "")),
                str(candidate.get("court", "")),
                str(candidate.get("absolute_url", "")),
            ]
        ).lower()

        # Fail closed by default for decoys and weak matches.
        company_ok = bool(company and company in haystack)
        court_ok = (not court) or (court in haystack)

        reject_reasons = []
        if not company_ok:
            reject_reasons.append("company_mismatch")
        if not court_ok:
            reject_reasons.append("court_mismatch")

        return {
            "passed": company_ok and court_ok,
            "reject_reasons": reject_reasons,
            "score": 1.0 if (company_ok and court_ok) else 0.0,
        }
