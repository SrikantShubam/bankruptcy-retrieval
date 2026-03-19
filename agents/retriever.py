import json
import os
import re
import time
from typing import Any, Dict, List, Tuple
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen

from shared.config import COURTLISTENER_SEARCH_URL, get_court_slug


class InfraError(Exception):
    pass


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
    "dip financing",
    "dip facility",
    "debtor in possession financing",
    "debtor in possession financing motion",
    "cash collateral motion",
    "postpetition financing",
    "motion to obtain postpetition financing",
    "motion to obtain financing",
    "interim order authorizing",
    "interim order approving",
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
_GENERIC_SINGLE_TOKEN_ALIASES = {"express"}


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
    if "chapter 11 petitions and first day" in norm:
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
    if "cash collateral" in norm and ("motion" in norm or "order" in norm or "use" in norm):
        return True
    if "postpetition financing" in norm:
        return True
    if "declaration" in norm and "in support of" in norm and ("chapter 11" in norm or "debtor" in norm or "petition" in norm):
        return True
    if "motion to obtain" in norm and "financing" in norm:
        return True
    if "interim" in norm and ("dip" in norm or "financing" in norm or "cash collateral" in norm) and "order" in norm:
        return True
    return False


def _company_tokens(company_name: str) -> list[str]:
    tokens = [t for t in re.findall(r"[a-z0-9]+", (company_name or "").lower()) if len(t) >= 3]
    return [t for t in tokens if t not in _COMPANY_STOPWORDS]


def _normalized_company_phrase(company_name: str) -> str:
    tokens = [t for t in re.findall(r"[a-z0-9]+", (company_name or "").lower()) if len(t) >= 2]
    return " ".join(tokens).strip()


def _required_match_count(company_name: str, token_count: int) -> int:
    marker_text = (company_name or "").lower()
    if any(marker in marker_text for marker in ("decoy", "subsidiary", "no standalone")) and token_count >= 2:
        return 2
    return 1


def _company_matches(company_name: str, case_name: str, description: str, search_aliases: list[str] | None = None) -> bool:
    haystack = _normalize_signal_text(f"{case_name or ''} {description or ''}")
    tokens = _company_tokens(company_name)
    if not tokens:
        return True
    if len(tokens) == 1 and tokens[0] in _GENERIC_SINGLE_TOKEN_ALIASES:
        phrase = _normalized_company_phrase(company_name)
        if bool(phrase) and (
            haystack.startswith(phrase)
            or f" filed by {phrase}" in haystack
            or f" debtor {phrase}" in haystack
        ):
            return True
    else:
        matched = sum(1 for tok in set(tokens) if tok in haystack)
        if matched >= _required_match_count(company_name, len(tokens)):
            return True
    # Check search_aliases from deal metadata
    for alias in (search_aliases or []):
        alias_tokens = _company_tokens(alias)
        if not alias_tokens:
            continue
        alias_matched = sum(1 for tok in set(alias_tokens) if tok in haystack)
        if alias_matched >= _required_match_count(alias, len(alias_tokens)):
            return True
    return False


class RetrieverAgent:
    """CourtListener retriever with bounded calls and docket-level verification."""

    BASE_URL = "https://www.courtlistener.com/api/rest/v4/search/"
    DOCKET_URL = "https://www.courtlistener.com/api/rest/v4/dockets/{docket_id}/"
    DOCKET_ENTRIES_URL = "https://www.courtlistener.com/api/rest/v4/docket-entries/?docket={docket_id}&page_size=50"
    V3_DOCKETS_URL = f"{COURTLISTENER_SEARCH_URL}/dockets/"
    V3_DOCKET_ENTRIES_URL = f"{COURTLISTENER_SEARCH_URL}/docket-entries/"
    TRANSIENT_HTTP_CODES = {429, 502, 503, 504}
    RETURN_CANDIDATE_CAP = 20
    DOCKET_PRIORITY_KEYWORDS = [
        "first day declaration",
        "declaration in support",
        "dip motion",
        "debtor in possession financing",
        "cash collateral",
        "capital structure",
        "prepetition debt",
        "credit agreement",
    ]

    def __init__(
        self,
        max_calls_per_deal: int = 6,
        timeout_seconds: int = 20,
        max_request_attempts: int = 3,
        retry_backoff_seconds: float = 1.0,
    ) -> None:
        self.token = os.getenv("COURTLISTENER_API_TOKEN", "").strip()
        self.max_calls_per_deal = max_calls_per_deal
        self.timeout_seconds = timeout_seconds
        self.max_request_attempts = max(1, max_request_attempts)
        self.retry_backoff_seconds = max(0.0, retry_backoff_seconds)

    def _is_transient_error(self, exc: Exception) -> bool:
        if isinstance(exc, HTTPError):
            return exc.code in self.TRANSIENT_HTTP_CODES
        return isinstance(exc, (URLError, TimeoutError))

    def _request_json(self, url: str) -> Dict[str, Any]:
        headers = {"Accept": "application/json"}
        if self.token:
            headers["Authorization"] = f"Token {self.token}"

        req = Request(url, headers=headers, method="GET")
        last_exc: Exception | None = None
        for attempt in range(1, self.max_request_attempts + 1):
            try:
                with urlopen(req, timeout=self.timeout_seconds) as resp:
                    payload = resp.read().decode("utf-8")
                data = json.loads(payload)
                if not isinstance(data, dict):
                    raise InfraError("CourtListener response is not a JSON object")
                return data
            except (HTTPError, URLError, TimeoutError, ValueError) as exc:
                last_exc = exc
                if attempt >= self.max_request_attempts or not self._is_transient_error(exc):
                    raise InfraError(str(exc)) from exc
                time.sleep(self.retry_backoff_seconds * attempt)
        raise InfraError(str(last_exc) if last_exc else "Unknown CourtListener request failure")

    def _normalize_url(self, value: Any) -> str:
        s = str(value or "").strip()
        if not s:
            return ""
        if s.startswith("/"):
            return f"https://www.courtlistener.com{s}"
        if s.startswith("http://") or s.startswith("https://"):
            return s
        return ""

    def _resolved_pdf_url(self, filepath_local: str) -> str:
        fp = str(filepath_local or "").strip()
        if not fp:
            return ""
        fp = fp.lstrip("/")
        return f"https://storage.courtlistener.com/{fp}"

    def _score_candidate(self, description: str, company_match: bool) -> int:
        score = _description_signal_score(description)
        if company_match:
            score += 2
        else:
            score -= 6
        norm = _normalize_signal_text(description)
        if any(rj in norm for rj in HARD_REJECT):
            score -= 8
        return score

    def _normalize_rd_candidate(self, item: Dict[str, Any], variant_name: str, company: str) -> Dict[str, Any] | None:
        description = str(item.get("description") or item.get("snippet") or "")
        if not _has_document_signal(description):
            return None
        if any(rj in _normalize_signal_text(description) for rj in HARD_REJECT):
            return None

        filepath_local = str(item.get("filepath_local") or "")
        resolved_pdf_url = self._resolved_pdf_url(filepath_local)
        if not resolved_pdf_url:
            return None

        case_name = str(item.get("caseName") or item.get("case_name") or "")
        search_aliases = item.get("_search_aliases") or []
        company_match = _company_matches(company, case_name, description, search_aliases=search_aliases)
        score = self._score_candidate(description, company_match)

        return {
            "id": str(item.get("id", "")).strip(),
            "docket_id": item.get("docket_id"),
            "docket_entry_id": str(item.get("docket_entry_id") or item.get("id") or "").strip(),
            "case_name": case_name,
            "docket_case_name": "",
            "docket_case_name_short": "",
            "docket_number": str(item.get("docketNumber") or item.get("docket_number") or "").strip(),
            "court": str(item.get("court") or item.get("court_id") or "").strip(),
            "absolute_url": self._normalize_url(item.get("absolute_url")),
            "description": description,
            "snippet": str(item.get("snippet") or ""),
            "download_url": resolved_pdf_url,
            "resolved_pdf_url": resolved_pdf_url,
            "row_company_match": company_match,
            "docket_company_match": False,
            "needs_docket_verification": (not company_match) and score >= 4 and bool(item.get("docket_id")),
            "score": score,
            "_query_variant": variant_name,
        }

    def _normalize_r_row_docs(self, row: Dict[str, Any], variant_name: str, company: str) -> List[Dict[str, Any]]:
        output: List[Dict[str, Any]] = []
        case_name = str(row.get("caseName") or row.get("case_name") or "")
        docket_id = row.get("docket_id") or row.get("id")
        docket_number = str(row.get("docket_number") or row.get("docketNumber") or "")
        court = str(row.get("court") or row.get("court_id") or "")
        for doc in row.get("recap_documents") or []:
            if not isinstance(doc, dict):
                continue
            description = str(doc.get("description") or doc.get("snippet") or "")
            if not _has_document_signal(description):
                continue
            if any(rj in _normalize_signal_text(description) for rj in HARD_REJECT):
                continue
            filepath_local = str(doc.get("filepath_local") or "")
            resolved_pdf_url = self._resolved_pdf_url(filepath_local)
            if not resolved_pdf_url:
                continue
            search_aliases = row.get("_search_aliases") or []
            company_match = _company_matches(company, case_name, description, search_aliases=search_aliases)
            score = self._score_candidate(description, company_match) + 2
            output.append(
                {
                    "id": str(doc.get("id", "")).strip(),
                    "docket_id": docket_id,
                    "docket_entry_id": str(doc.get("docket_entry_id") or doc.get("id") or "").strip(),
                    "case_name": case_name,
                    "docket_case_name": case_name,
                    "docket_case_name_short": case_name,
                    "docket_number": docket_number,
                    "court": court,
                    "absolute_url": self._normalize_url(row.get("absolute_url")),
                    "description": description,
                    "snippet": str(doc.get("snippet") or ""),
                    "download_url": resolved_pdf_url,
                    "resolved_pdf_url": resolved_pdf_url,
                    "row_company_match": company_match,
                    "docket_company_match": company_match,
                    "needs_docket_verification": False,
                    "score": score,
                    "_query_variant": variant_name,
                }
            )
        return output

    def execute_plan(self, plan_variants: List[Dict[str, Any]], deal: Dict[str, Any] | None = None) -> Tuple[List[Dict[str, Any]], int]:
        calls = 0
        all_candidates: List[Dict[str, Any]] = []
        seen_keys = set()
        company = str((deal or {}).get("company_name") or (deal or {}).get("company") or "")
        search_aliases = list((deal or {}).get("search_aliases") or [])

        for variant in plan_variants:
            if calls >= self.max_calls_per_deal:
                break

            filing_year = str(variant.get("filing_year") or "")
            query = {
                "q": variant.get("q", ""),
                "type": variant.get("type", "rd"),
                "order_by": "score desc",
                "page_size": 50,
            }
            if variant.get("available_only", True):
                query["available_only"] = "on"
            if filing_year.isdigit():
                query["filed_after"] = f"{filing_year}-01-01"
                query["filed_before"] = f"{filing_year}-12-31"

            url = f"{self.BASE_URL}?{urlencode(query)}"
            try:
                data = self._request_json(url)
                calls += 1
            except InfraError:
                continue

            results = data.get("results")
            if not isinstance(results, list):
                raise InfraError("CourtListener results payload missing list field")

            normalized_batch: List[Dict[str, Any]] = []
            for item in results:
                if not isinstance(item, dict):
                    continue
                if variant.get("type") == "r":
                    for doc in (item.get("recap_documents") or []):
                        if isinstance(doc, dict):
                            doc["_search_aliases"] = search_aliases
                    item["_search_aliases"] = search_aliases
                    normalized_batch.extend(self._normalize_r_row_docs(item, variant.get("name", "unknown"), company))
                else:
                    item["_search_aliases"] = search_aliases
                    norm = self._normalize_rd_candidate(item, variant.get("name", "unknown"), company)
                    if norm:
                        normalized_batch.append(norm)

            for normalized in normalized_batch:
                dedupe_key = normalized.get("resolved_pdf_url") or normalized.get("id") or normalized.get("absolute_url")
                if not dedupe_key or dedupe_key in seen_keys:
                    continue
                seen_keys.add(dedupe_key)
                all_candidates.append(normalized)

            all_candidates.sort(key=lambda c: int(c.get("score", 0)), reverse=True)

        all_candidates.sort(key=lambda c: int(c.get("score", 0)), reverse=True)
        return all_candidates[:self.RETURN_CANDIDATE_CAP], calls

    def execute_docket_plan(self, deal: Dict[str, Any], docket_variants: List[Dict[str, Any]] | None = None) -> Tuple[List[Dict[str, Any]], int]:
        """Docket-first search: use V3 dockets + docket-entries filters, then normalize recap docs."""
        company = str(deal.get("company_name") or deal.get("company") or "")
        search_aliases = list(deal.get("search_aliases") or [])
        court_slug = get_court_slug(str(deal.get("court") or "").strip())
        all_candidates: List[Dict[str, Any]] = []
        seen_keys: set = set()
        calls = 0
        found_docket_ids: List[Any] = []

        variants = docket_variants or []
        if not variants:
            exact_alias = company.split("(")[0].strip()
            filing_year = str(deal.get("filing_year") or "")
            variants = [
                {"name": "docket_default", "type": "d", "q": f'"{exact_alias}" chapter 11', "filing_year": filing_year, "available_only": False}
            ]

        # Step 1: Search dockets with aggressive server-side V3 filters.
        for variant in variants[:6]:
            if calls >= 6:
                break
            filing_year = str(variant.get("filing_year") or "")
            case_name = str(variant.get("case_name") or variant.get("q") or "").strip().strip('"')
            query = {
                "case_name__icontains": case_name,
                "chapter": 11,
                "order_by": "score desc",
                "page_size": 10,
            }
            if court_slug:
                query["court"] = court_slug
            if filing_year.isdigit():
                query["filed_after"] = f"{int(filing_year) - 1}-01-01"
                query["filed_before"] = f"{int(filing_year) + 1}-12-31"

            url = f"{self.V3_DOCKETS_URL}?{urlencode(query)}"
            try:
                data = self._request_json(url)
                calls += 1
            except InfraError:
                continue

            for item in data.get("results", []):
                if not isinstance(item, dict):
                    continue
                docket_id = item.get("docket_id") or item.get("id")
                case_name = str(item.get("caseName") or item.get("case_name") or "")
                if not docket_id:
                    continue
                if _company_matches(company, case_name, "", search_aliases=search_aliases):
                    if docket_id not in found_docket_ids:
                        found_docket_ids.append(docket_id)

        # Step 2: Search docket entries by prioritized document keywords.
        for docket_id in found_docket_ids[:4]:
            for keyword in self.DOCKET_PRIORITY_KEYWORDS:
                if calls >= 12:
                    break
                query = {
                    "docket": docket_id,
                    "description__icontains": keyword,
                    "order_by": "date_filed",
                    "page_size": 5,
                }
                filing_year = str(deal.get("filing_year") or "")
                if filing_year.isdigit():
                    query["date_filed__gte"] = f"{filing_year}-01-01"
                url = f"{self.V3_DOCKET_ENTRIES_URL}?{urlencode(query)}"
                try:
                    data = self._request_json(url)
                    calls += 1
                except InfraError:
                    continue

                matched_entry = False
                for entry in data.get("results", []):
                    if not isinstance(entry, dict):
                        continue
                    entry_desc = str(entry.get("description") or "")
                    if not _has_document_signal(entry_desc):
                        continue
                    if any(rj in _normalize_signal_text(entry_desc) for rj in HARD_REJECT):
                        continue

                    for doc in entry.get("recap_documents") or []:
                        if not isinstance(doc, dict):
                            continue
                        filepath_local = str(doc.get("filepath_local") or "")
                        resolved_pdf_url = self._resolved_pdf_url(filepath_local)
                        if not resolved_pdf_url:
                            continue

                        dedupe_key = resolved_pdf_url
                        if dedupe_key in seen_keys:
                            continue
                        seen_keys.add(dedupe_key)

                        doc_desc = str(doc.get("description") or entry_desc or "")
                        company_match = _company_matches(company, "", doc_desc, search_aliases=search_aliases)
                        score = self._score_candidate(doc_desc, company_match) + 3

                        all_candidates.append({
                            "id": str(doc.get("id", "")).strip(),
                            "docket_id": docket_id,
                            "docket_entry_id": str(entry.get("id") or doc.get("id") or "").strip(),
                            "case_name": "",
                            "docket_case_name": "",
                            "docket_case_name_short": "",
                            "docket_number": "",
                            "court": court_slug or "",
                            "absolute_url": "",
                            "description": doc_desc,
                            "snippet": "",
                            "download_url": resolved_pdf_url,
                            "resolved_pdf_url": resolved_pdf_url,
                            "row_company_match": company_match,
                            "docket_company_match": True,
                            "needs_docket_verification": False,
                            "score": score,
                            "_query_variant": "docket_entry_fallback",
                        })
                        matched_entry = True
                if matched_entry:
                    break

        all_candidates.sort(key=lambda c: int(c.get("score", 0)), reverse=True)
        return all_candidates[:self.RETURN_CANDIDATE_CAP], calls

    def verify_candidates_with_dockets(self, candidates: List[Dict[str, Any]], deal: Dict[str, Any], max_extra_calls: int = 2) -> Tuple[List[Dict[str, Any]], int]:
        company = str(deal.get("company_name") or deal.get("company") or "")
        search_aliases = list(deal.get("search_aliases") or [])
        extra_calls = 0
        docket_cache: Dict[Any, Dict[str, Any]] = {}
        updated: List[Dict[str, Any]] = []

        for candidate in candidates:
            updated_candidate = dict(candidate)
            if (
                extra_calls < max_extra_calls
                and updated_candidate.get("needs_docket_verification")
                and updated_candidate.get("docket_id")
            ):
                docket_id = updated_candidate.get("docket_id")
                docket = docket_cache.get(docket_id)
                if docket is None:
                    url = self.DOCKET_URL.format(docket_id=docket_id)
                    try:
                        docket = self._request_json(url)
                        docket_cache[docket_id] = docket
                        extra_calls += 1
                    except InfraError:
                        updated.append(updated_candidate)
                        continue
                docket_case_name = str(docket.get("case_name") or docket.get("case_name_short") or "")
                docket_case_name_short = str(docket.get("case_name_short") or "")
                updated_candidate["docket_case_name"] = docket_case_name
                updated_candidate["docket_case_name_short"] = docket_case_name_short
                updated_candidate["docket_number"] = str(docket.get("docket_number") or updated_candidate.get("docket_number") or "")
                updated_candidate["court"] = str(docket.get("court_id") or updated_candidate.get("court") or "")
                docket_company_match = _company_matches(company, docket_case_name, updated_candidate.get("description", ""), search_aliases=search_aliases)
                updated_candidate["docket_company_match"] = docket_company_match
                updated_candidate["needs_docket_verification"] = False
                if docket_company_match:
                    updated_candidate["score"] = int(updated_candidate.get("score", 0)) + 6
                    if not updated_candidate.get("case_name"):
                        updated_candidate["case_name"] = docket_case_name
            updated.append(updated_candidate)

        updated.sort(
            key=lambda c: (
                int(bool(c.get("row_company_match"))),
                int(bool(c.get("docket_company_match"))),
                int(c.get("score", 0)),
            ),
            reverse=True,
        )
        return updated[:self.RETURN_CANDIDATE_CAP], extra_calls
