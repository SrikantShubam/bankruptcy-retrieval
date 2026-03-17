from dataclasses import dataclass
from typing import Any, Dict, List


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
        court = (deal.get("court") or "").strip()

        strict_terms = [t for t in [company, filing_year, court, "chapter 11", "first day declaration", "dip motion"] if t]
        broad_terms = [t for t in [company, filing_year, "bankruptcy", "chapter 11", "first day", "dip"] if t]

        variants = [
            {
                "name": "strict_rd",
                "type": "rd",
                "q": " ".join(strict_terms),
            },
            {
                "name": "broad_rd",
                "type": "rd",
                "q": " ".join(broad_terms),
            },
            {
                "name": "broad_r",
                "type": "r",
                "q": " ".join(broad_terms),
            },
        ]

        return QueryPlan(deal_id=deal_id, variants=variants)
