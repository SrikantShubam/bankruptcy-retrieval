import unittest
from unittest.mock import patch

from agents.retriever import RetrieverAgent


class RetrieverDocketTests(unittest.TestCase):
    def test_execute_docket_plan_uses_v3_docket_filters_and_returns_candidate(self):
        agent = RetrieverAgent(max_calls_per_deal=18)
        deal = {
            "deal_id": "tgi-fridays-2024",
            "company_name": "TGI Fridays, Inc.",
            "search_aliases": ["TGI Friday's"],
            "filing_year": 2024,
            "court": "N.D. Tex.",
        }
        variants = [
            {
                "name": "docket_year_bounded",
                "type": "d",
                "q": "\"TGI Friday's\" chapter 11",
                "case_name": "TGI Friday's",
                "filing_year": "2024",
                "available_only": False,
            }
        ]

        seen_urls = []

        def fake_request(url: str):
            seen_urls.append(url)
            if "/api/rest/v3/dockets/" in url:
                return {
                    "results": [
                        {
                            "id": 123,
                            "case_name": "T.G.I. Friday's of Texas, LLC",
                            "court": "txnb",
                        }
                    ]
                }
            if "/api/rest/v3/docket-entries/" in url:
                return {
                    "results": [
                        {
                            "id": 456,
                            "description": "Declaration of CRO in Support of Chapter 11 Petitions and First Day Motions",
                            "recap_documents": [
                                {
                                    "id": 789,
                                    "description": "Declaration of CRO in Support of Chapter 11 Petitions and First Day Motions",
                                    "filepath_local": "/recap/test.pdf",
                                }
                            ],
                        }
                    ]
                }
            raise AssertionError(f"unexpected url {url}")

        with patch.object(agent, "_request_json", side_effect=fake_request):
            candidates, calls = agent.execute_docket_plan(deal, docket_variants=variants)

        self.assertEqual(2, calls)
        self.assertEqual(1, len(candidates))
        self.assertEqual("https://storage.courtlistener.com/recap/test.pdf", candidates[0]["resolved_pdf_url"])
        self.assertTrue(any("case_name__icontains=TGI+Friday%27s" in url for url in seen_urls))
        self.assertTrue(any("court=txnd" in url for url in seen_urls))
        self.assertTrue(any("chapter=11" in url for url in seen_urls))
        self.assertTrue(any("description__icontains=first+day+declaration" in url or "description__icontains=declaration+in+support" in url for url in seen_urls))


if __name__ == "__main__":
    unittest.main()
