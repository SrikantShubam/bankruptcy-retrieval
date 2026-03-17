from dataclasses import dataclass
from typing import Any, Dict, List
import re

_COMPANY_QUERY_STOPWORDS = {
    'inc', 'incorporated', 'llc', 'corp', 'corporation', 'company', 'co', 'holdings',
    'group', 'financial', 'finance', 'pharma', 'systems', 'brands', 'technology', 'technologies',
    'networks', 'services', 'entertainment', 'the', 'and', 'for'
}


def _core_alias(company: str) -> str:
    tokens = [t for t in re.findall(r"[A-Za-z0-9]+", company or "") if len(t) >= 3]
    filtered = [t for t in tokens if t.lower() not in _COMPANY_QUERY_STOPWORDS]
    if not filtered:
        filtered = tokens
    return " ".join(filtered[:2]).strip()


@dataclass
class QueryPlan:
    """Staged retrieval plan with strict-first then broadened fallback variants."""

    deal_id: str
    variants: List[Dict[str, Any]]


class PlannerAgent:
    def build_plan(self, deal: Dict[str, Any]) -> QueryPlan:
        deal_id = str(deal.get("deal_id", "unknown-deal"))
        company = (deal.get("company_name") or deal.get("company") or "").strip()
        filing_year = str(deal.get("filing_year") or "").strip()
        is_decoy = "decoy" in deal_id.lower() or "decoy" in company.lower()

        exact_alias = company.split("(")[0].strip()
        stripped_alias = re.sub(r"[^A-Za-z0-9 ]+", " ", exact_alias)
        stripped_alias = re.sub(r"\s+", " ", stripped_alias).strip()
        loose_alias = _core_alias(stripped_alias or exact_alias)
        exact_tokens = [t for t in re.findall(r"[A-Za-z0-9]+", stripped_alias or exact_alias) if len(t) >= 3]
        first_token_alias = exact_tokens[0] if exact_tokens else ""

        candidate_queries = [
            ("strict_rd_first_day", "rd", f'"{exact_alias}" "first day declaration"'),
            ("strict_rd_ch11", "rd", f'"{exact_alias}" "chapter 11 petitions and first day motions"'),
            ("strict_rd_support", "rd", f'"{exact_alias}" "declaration in support of chapter 11 petitions"'),
            ("strict_rd_dip", "rd", f'"{exact_alias}" "debtor in possession financing"'),
            ("strict_rd_cash", "rd", f'"{exact_alias}" "cash collateral"'),
            ("strict_rd_postpetition", "rd", f'"{exact_alias}" "postpetition financing"'),
            ("broad_r", "r", f'"{exact_alias}" "chapter 11"'),
        ]
        if not is_decoy and loose_alias and loose_alias.lower() != exact_alias.lower():
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
