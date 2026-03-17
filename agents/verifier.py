import re
from typing import Any, Dict

DOC_KEYWORDS = [
    "first day declaration",
    "declaration in support of first day",
    "declaration in support of chapter 11 petitions",
    "chapter 11 petitions and first day motions",
    "first day motions",
    "first day motion",
    "first day pleadings",
    "first day papers",
    "first day matters",
    "dip motion",
    "debtor in possession financing",
    "debtor in possession financing motion",
    "cash collateral motion",
    "postpetition financing",
]

HARD_REJECT = [
    "committee",
    "objection",
    "opposition",
    "notice of",
    "retention",
    "application to employ",
    "monthly operating report",
    "monthly fee statement",
    "designation of record",
    "appeal",
    "equity interest holders",
]

_COMPANY_STOPWORDS = {
    "inc", "inc.", "llc", "l.l.c.", "corp", "corporation", "company", "co", "co.",
    "holdings", "group", "financial", "finance", "pharma", "systems", "brands", "technology", "technologies", "networks", "services", "entertainment", "the", "and", "for",
}


def _normalize_signal_text(text: str) -> str:
    value = (text or "").lower().replace("&", " and ")
    value = re.sub(r"[^a-z0-9]+", " ", value)
    return re.sub(r"\s+", " ", value).strip()


def _description_signal_score(text: str) -> int:
    norm = _normalize_signal_text(text)
    score = 0
    if "first day declaration" in norm:
        score += 10
    if "declaration in support of first day" in norm:
        score += 8
    if "declaration in support of chapter 11 petitions" in norm:
        score += 8
    if "chapter 11 petitions and first day motions" in norm:
        score += 7
    if "in support of first day motions" in norm:
        score += 7
    if "first day motions" in norm or "first day motion" in norm:
        score += 6
    if "first day pleadings" in norm or "first day papers" in norm:
        score += 5
    if "dip motion" in norm:
        score += 5
    if "debtor in possession financing" in norm:
        score += 5
    if "postpetition financing" in norm:
        score += 5
    if "cash collateral motion" in norm or "use cash collateral" in norm:
        score += 4
    if "declaration" in norm and "in support of" in norm and ("debtor" in norm or "chapter 11" in norm):
        score += 4
    return score


def _has_document_signal(text: str) -> bool:
    norm = _normalize_signal_text(text)
    if any(kw in norm for kw in DOC_KEYWORDS):
        return True
    if "first day" in norm and any(tok in norm for tok in ("declaration", "pleading", "petition", "motion")):
        return True
    if "cash collateral" in norm and "motion" in norm:
        return True
    if "postpetition financing" in norm:
        return True
    return False


def _company_tokens(company_name: str) -> list[str]:
    tokens = [t for t in re.findall(r"[a-z0-9]+", (company_name or "").lower()) if len(t) >= 3]
    return [t for t in tokens if t not in _COMPANY_STOPWORDS]


def _required_match_count(company_name: str, token_count: int) -> int:
    marker_text = (company_name or "").lower()
    if any(marker in marker_text for marker in ("decoy", "subsidiary", "no standalone")) and token_count >= 2:
        return 2
    return 1


def _company_matches(company_name: str, haystack: str) -> bool:
    tokens = _company_tokens(company_name)
    haystack_norm = _normalize_signal_text(haystack)
    if not tokens:
        return True
    matched = sum(1 for tok in set(tokens) if tok in haystack_norm)
    return matched >= _required_match_count(company_name, len(tokens))


class VerifierAgent:
    """Deterministic verifier with optional docket-level evidence."""

    def verify(self, deal: Dict[str, Any], candidate: Dict[str, Any]) -> Dict[str, Any]:
        company = (deal.get("company_name") or deal.get("company") or "").lower()
        description = str(candidate.get("description", "") or candidate.get("snippet", "") or "")
        row_haystack = " ".join(
            [
                str(candidate.get("case_name", "")),
                str(candidate.get("docket_number", "")),
                str(candidate.get("court", "")),
                str(candidate.get("absolute_url", "")),
                description,
                str(candidate.get("snippet", "")),
            ]
        )
        docket_haystack = " ".join(
            [
                str(candidate.get("docket_case_name", "")),
                str(candidate.get("docket_case_name_short", "")),
                str(candidate.get("docket_number", "")),
            ]
        )

        row_company_match = bool(candidate.get("row_company_match")) or _company_matches(company, row_haystack)
        docket_company_match = bool(candidate.get("docket_company_match")) or _company_matches(company, docket_haystack)
        has_signal = _has_document_signal(description)
        is_noise = any(rj in _normalize_signal_text(description) for rj in HARD_REJECT)

        raw_score = _description_signal_score(description)
        if row_company_match:
            raw_score += 2
        if docket_company_match:
            raw_score += 4
        if is_noise:
            raw_score -= 6

        norm_score = max(0.0, min(1.0, raw_score / 12.0))
        needs_docket_verification = has_signal and not row_company_match and bool(candidate.get("docket_id"))
        passed = has_signal and not is_noise and raw_score >= 5 and (row_company_match or docket_company_match)

        reject_reasons = []
        if not has_signal:
            reject_reasons.append("missing_target_document_signal")
        if not (row_company_match or docket_company_match):
            reject_reasons.append("company_mismatch")
        if is_noise:
            reject_reasons.append("hard_reject_noise")

        return {
            "passed": passed,
            "reject_reasons": reject_reasons,
            "score": norm_score,
            "raw_score": raw_score,
            "row_company_match": row_company_match,
            "docket_company_match": docket_company_match,
            "needs_docket_verification": needs_docket_verification,
        }
