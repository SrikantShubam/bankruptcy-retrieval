import json
import unittest
from unittest.mock import patch
from urllib.error import HTTPError

from agents.retriever import InfraError, RetrieverAgent


class _FakeResponse:
    def __init__(self, payload, status=200):
        self._payload = payload
        self.status = status

    def read(self):
        return json.dumps(self._payload).encode("utf-8")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, tb):
        return False


class RetrieverRetryTests(unittest.TestCase):
    def test_request_json_retries_transient_http_502(self):
        agent = RetrieverAgent()
        calls = {"count": 0}

        def flaky_urlopen(req, timeout):
            calls["count"] += 1
            if calls["count"] < 3:
                raise HTTPError(req.full_url, 502, "Bad Gateway", hdrs=None, fp=None)
            return _FakeResponse({"results": []})

        with patch("agents.retriever.urlopen", side_effect=flaky_urlopen):
            data = agent._request_json("https://example.com/test")

        self.assertEqual({"results": []}, data)
        self.assertEqual(3, calls["count"])

    def test_request_json_raises_after_retry_budget_exhausted(self):
        agent = RetrieverAgent()

        def always_fail(req, timeout):
            raise HTTPError(req.full_url, 502, "Bad Gateway", hdrs=None, fp=None)

        with patch("agents.retriever.urlopen", side_effect=always_fail):
            with self.assertRaises(InfraError):
                agent._request_json("https://example.com/test")

    def test_execute_plan_continues_after_one_variant_fails(self):
        agent = RetrieverAgent(max_calls_per_deal=4)
        variants = [
            {"name": "first", "type": "rd", "q": "first", "filing_year": "2023"},
            {"name": "second", "type": "rd", "q": "second", "filing_year": "2023"},
        ]

        responses = [
            InfraError("HTTP Error 502: Bad Gateway"),
            {"results": []},
        ]

        def fake_request(url):
            result = responses.pop(0)
            if isinstance(result, Exception):
                raise result
            return result

        with patch.object(agent, "_request_json", side_effect=fake_request):
            candidates, calls = agent.execute_plan(variants, deal={"company_name": "Example Co"})

        self.assertEqual([], candidates)
        self.assertEqual(1, calls)

    def test_execute_plan_does_not_stop_after_two_same_type_matches(self):
        agent = RetrieverAgent(max_calls_per_deal=3)
        variants = [
            {"name": "strict_rd_first_day", "type": "rd", "q": "first", "filing_year": "2024"},
            {"name": "strict_rd_declaration", "type": "rd", "q": "declaration", "filing_year": "2024"},
            {"name": "strict_rd_dip", "type": "rd", "q": "dip", "filing_year": "2024"},
        ]

        responses = [
            {
                "results": [
                    {
                        "id": "1",
                        "docket_id": "100",
                        "description": "Declaration of CRO in Support of Chapter 11 Petitions and First Day Motions",
                        "filepath_local": "/recap/a.pdf",
                        "caseName": "Conn's, Inc.",
                        "court": "txsb",
                    }
                ]
            },
            {
                "results": [
                    {
                        "id": "2",
                        "docket_id": "100",
                        "description": "Declaration of Norman Miller in Support of Debtors Chapter 11 Petitions and First Day Pleadings",
                        "filepath_local": "/recap/b.pdf",
                        "caseName": "Conn's, Inc.",
                        "court": "txsb",
                    }
                ]
            },
            {
                "results": [
                    {
                        "id": "3",
                        "docket_id": "100",
                        "description": "Declaration in Support of Debtors Motion to Obtain Postpetition Financing",
                        "filepath_local": "/recap/c.pdf",
                        "caseName": "Conn's, Inc.",
                        "court": "txsb",
                    }
                ]
            },
        ]

        with patch.object(agent, "_request_json", side_effect=responses):
            candidates, calls = agent.execute_plan(
                variants,
                deal={
                    "company_name": "Conn's, Inc.",
                    "required_doc_types": ["first_day_declaration", "dip_motion"],
                },
            )

        self.assertEqual(3, calls)
        self.assertEqual(3, len(candidates))


if __name__ == "__main__":
    unittest.main()
