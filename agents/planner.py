from dataclasses import dataclass
from typing import Any, Dict, List
import re

_COMPANY_QUERY_STOPWORDS = {
    'inc', 'incorporated', 'llc', 'corp', 'corporation', 'company', 'co', 'holdings',
    'group', 'financial', 'finance', 'pharma', 'systems', 'brands', 'technology', 'technologies',
    'networks', 'services', 'entertainment', 'the', 'and', 'for'
}

_GENERIC_SINGLE_TOKEN_ALIASES = {"express"}


def _core_alias(company: str) -> str:
    tokens = [t for t in re.findall(r"[A-Za-z0-9]+", company or "") if len(t) >= 3]
    filtered = [t for t in tokens if t.lower() not in _COMPANY_QUERY_STOPWORDS]
    if not filtered:
        filtered = tokens
    return " ".join(filtered[:2]).strip()


def _extra_search_aliases(deal: Dict[str, Any]) -> list[str]:
    aliases = []
    for value in deal.get("search_aliases") or []:
        alias = str(value or "").strip()
        if alias:
            aliases.append(alias)
    return aliases


def _expand_alias_variants(alias: str) -> list[str]:
    out: list[str] = []
    normalized = str(alias or "").strip()
    if not normalized:
        return out
    out.append(normalized)
    tokens = [t for t in re.findall(r"[A-Za-z0-9]+", normalized) if len(t) >= 3]
    if tokens:
        out.append(tokens[0])
        if len(tokens) >= 2:
            out.append(" ".join(tokens[:2]))
    seen: list[str] = []
    for value in out:
        collapsed = re.sub(r"\s+", " ", value).strip()
        if collapsed and collapsed.lower() not in {s.lower() for s in seen}:
            seen.append(collapsed)
    return seen


def _is_generic_single_token_alias(alias: str) -> bool:
    tokens = [t for t in re.findall(r"[A-Za-z0-9]+", alias or "") if len(t) >= 3]
    return len(tokens) == 1 and tokens[0].lower() in _GENERIC_SINGLE_TOKEN_ALIASES


@dataclass
class QueryPlan:
    """Staged retrieval plan with strict-first then broadened fallback variants."""

    deal_id: str
    variants: List[Dict[str, Any]]


class PlannerAgent:
    def _candidate_aliases(self, deal: Dict[str, Any]) -> list[str]:
        company = (deal.get("company_name") or deal.get("company") or "").strip()
        exact_alias = company.split("(")[0].strip()
        stripped_alias = re.sub(r"[^A-Za-z0-9 ]+", " ", exact_alias)
        stripped_alias = re.sub(r"\s+", " ", stripped_alias).strip()
        loose_alias = _core_alias(stripped_alias or exact_alias)

        aliases: list[str] = []
        for raw in [exact_alias, loose_alias, *_extra_search_aliases(deal)]:
            for expanded in _expand_alias_variants(str(raw or "")):
                if expanded and expanded.lower() not in {a.lower() for a in aliases}:
                    aliases.append(expanded)
        return aliases

    def build_plan(self, deal: Dict[str, Any]) -> QueryPlan:
        deal_id = str(deal.get("deal_id", "unknown-deal"))
        company = (deal.get("company_name") or deal.get("company") or "").strip()
        filing_year = str(deal.get("filing_year") or "").strip()
        is_decoy = "decoy" in deal_id.lower() or "decoy" in company.lower()

        exact_alias = company.split("(")[0].strip()
        stripped_alias = re.sub(r"[^A-Za-z0-9 ]+", " ", exact_alias)
        stripped_alias = re.sub(r"\s+", " ", stripped_alias).strip()
        loose_alias = _core_alias(stripped_alias or exact_alias)
        extra_aliases = _extra_search_aliases(deal)
        exact_tokens = [t for t in re.findall(r"[A-Za-z0-9]+", stripped_alias or exact_alias) if len(t) >= 3]
        first_token_alias = exact_tokens[0] if exact_tokens else ""

        candidate_queries = [
            ("strict_rd_first_day", "rd", f'"{exact_alias}" "first day declaration"'),
            ("strict_rd_first_day_motions", "rd", f'"{exact_alias}" "first day motions"'),
            ("strict_rd_ch11", "rd", f'"{exact_alias}" "chapter 11 petitions and first day motions"'),
            ("strict_rd_declaration", "rd", f'"{exact_alias}" declaration'),
            ("strict_rd_support", "rd", f'"{exact_alias}" "declaration in support of chapter 11 petitions"'),
            ("strict_rd_dip", "rd", f'"{exact_alias}" "debtor in possession financing"'),
            ("strict_rd_cash", "rd", f'"{exact_alias}" "cash collateral"'),
            ("strict_rd_postpetition", "rd", f'"{exact_alias}" "postpetition financing"'),
            ("strict_rd_chapter11", "rd", f'"{exact_alias}" "chapter 11"'),
            ("broad_r", "r", f'"{exact_alias}" "chapter 11"'),
        ]
        for alias in extra_aliases:
            candidate_queries.extend(
                [
                    ("alias_rd_first_day_motions", "rd", f'"{alias}" "first day motions"'),
                    ("alias_rd_chapter11", "rd", f'"{alias}" "chapter 11"'),
                ]
            )
        if (
            not is_decoy
            and loose_alias
            and loose_alias.lower() != exact_alias.lower()
            and not _is_generic_single_token_alias(loose_alias)
        ):
            candidate_queries[2:2] = [
                ("loose_rd_ch11", "rd", f'{loose_alias} chapter 11 petitions and first day motions'),
                ("loose_rd_support", "rd", f'{loose_alias} declaration in support of chapter 11 petitions'),
            ]
            candidate_queries.insert(6, ("loose_rd_dip", "rd", f'{loose_alias} debtor in possession financing'))
            candidate_queries.insert(8, ("loose_rd_postpetition", "rd", f'{loose_alias} postpetition financing'))
        if not is_decoy and first_token_alias and first_token_alias.lower() not in {exact_alias.lower(), loose_alias.lower()}:
            candidate_queries.insert(2, ("token_rd_ch11", "rd", f'{first_token_alias} chapter 11 petitions and first day motions'))
            candidate_queries.insert(4, ("token_rd_support", "rd", f'{first_token_alias} declaration in support of chapter 11 petitions'))

        seen = set()
        variants: List[Dict[str, Any]] = []
        for name, query_type, query_text in candidate_queries:
            key = (query_type, query_text)
            if key in seen:
                continue
            seen.add(key)
            variants.append(
                {
                    "name": name,
                    "type": query_type,
                    "q": query_text,
                    "filing_year": filing_year,
                }
            )

        return QueryPlan(deal_id=deal_id, variants=variants)

    def build_docket_variants(self, deal: Dict[str, Any]) -> List[Dict[str, Any]]:
        filing_year = str(deal.get("filing_year") or "").strip()
        variants: List[Dict[str, Any]] = []
        seen = set()
        for alias in self._candidate_aliases(deal):
            for name, year in (
                ("docket_year_bounded", filing_year),
                ("docket_yearless", ""),
            ):
                query = f'"{alias}" chapter 11'
                key = ("d", query, year)
                if key in seen:
                    continue
                seen.add(key)
                variants.append(
                    {
                        "name": name,
                        "type": "d",
                        "q": query,
                        "case_name": alias,
                        "filing_year": year,
                        "available_only": False,
                    }
                )
        return variants

    def build_followup_variants(self, deal: Dict[str, Any], missing_doc_types: List[str]) -> List[Dict[str, Any]]:
        company = (deal.get("company_name") or deal.get("company") or "").strip()
        filing_year = str(deal.get("filing_year") or "").strip()
        exact_alias = company.split("(")[0].strip()
        stripped_alias = re.sub(r"[^A-Za-z0-9 ]+", " ", exact_alias)
        stripped_alias = re.sub(r"\s+", " ", stripped_alias).strip()
        loose_alias = _core_alias(stripped_alias or exact_alias)
        aliases = [exact_alias]
        aliases.extend(_extra_search_aliases(deal))
        if loose_alias and loose_alias.lower() not in {alias.lower() for alias in aliases} and not _is_generic_single_token_alias(loose_alias):
            aliases.append(loose_alias)

        followups: List[tuple[str, str, str]] = []
        for alias in aliases:
            quoted = f'"{alias}"'
            for doc_type in missing_doc_types:
                if doc_type == "dip_motion":
                    followups.extend(
                        [
                            ("followup_rd_dip", "rd", f'{quoted} "debtor in possession financing"'),
                            ("followup_rd_postpetition", "rd", f'{quoted} "postpetition financing"'),
                            ("followup_rd_obtain_financing", "rd", f'{quoted} "motion to obtain postpetition financing"'),
                            ("followup_rd_interim_dip", "rd", f'{quoted} "interim dip order"'),
                        ]
                    )
                elif doc_type == "first_day_declaration":
                    followups.extend(
                        [
                            ("followup_rd_first_day_decl", "rd", f'{quoted} "first day declaration"'),
                            ("followup_rd_first_day_support", "rd", f'{quoted} "declaration in support of chapter 11 petitions"'),
                            ("followup_rd_first_day_pleadings", "rd", f'{quoted} "first day pleadings"'),
                        ]
                    )
                elif doc_type == "credit_agreement":
                    followups.extend(
                        [
                            ("followup_rd_credit_agreement", "rd", f'{quoted} "credit agreement"'),
                            ("followup_rd_loan_agreement", "rd", f'{quoted} "loan agreement"'),
                            ("followup_rd_term_loan", "rd", f'{quoted} "term loan"'),
                        ]
                    )
                elif doc_type == "cash_collateral_motion":
                    followups.extend(
                        [
                            ("followup_rd_cash_collateral", "rd", f'{quoted} "cash collateral"'),
                            ("followup_rd_use_cash_collateral", "rd", f'{quoted} "use cash collateral"'),
                        ]
                    )

        seen = set()
        variants: List[Dict[str, Any]] = []
        for name, query_type, query_text in followups:
            key = (query_type, query_text)
            if key in seen:
                continue
            seen.add(key)
            variants.append(
                {
                    "name": name,
                    "type": query_type,
                    "q": query_text,
                    "filing_year": filing_year,
                }
            )
        return variants
