import unittest

import graph
from agents.verifier import VerifierAgent
from shared.telemetry import TelemetryCollector


class DProvenanceTests(unittest.TestCase):
    def test_generic_first_day_motion_is_not_a_declaration(self):
        value = (
            "Motion Regarding Chapter 11 First Day Motions - Debtors' Motion for Entry of "
            "(A) an Order Authorizing Debtors to File a Consolidated Creditor Matrix"
        )

        self.assertEqual("other_supporting", graph._normalize_doc_type(value))

    def test_wrong_case_bundle_does_not_count_as_true_positive(self):
        telemetry = TelemetryCollector()
        telemetry.record_terminal(
            {
                "deal_id": "caremax-2024",
                "pipeline_status": "DOWNLOADED",
                "selected_doc_types": ["first_day_declaration", "dip_motion"],
                "selected_documents": [
                    {
                        "normalized_doc_type": "first_day_declaration",
                        "same_case_confirmed": False,
                        "candidate_title": "Declaration ... Filed By Steward Health Care System LLC",
                    },
                    {
                        "normalized_doc_type": "dip_motion",
                        "same_case_confirmed": False,
                        "candidate_title": "DIP Motion ... Filed By Steward Health Care System LLC",
                    },
                ],
            }
        )

        report = telemetry.summarize(
            ground_truth={
                "caremax-2024": {
                    "has_financial_data": True,
                    "already_processed": False,
                    "required_doc_types": ["dip_motion", "first_day_declaration"],
                    "minimum_required_coverage": 2,
                }
            },
            total_api_calls=1,
            total_llm_calls=0,
        )

        self.assertEqual(0, report["TP"])
        self.assertEqual(1, report["FN"])

    def test_verifier_rejects_wrong_case_even_with_document_signal(self):
        verifier = VerifierAgent()
        result = verifier.verify(
            {"company_name": "CareMax, Inc."},
            {
                "description": "Declaration re: Declaration of John R. Castellano in Support of Debtors' Chapter 11 Petitions and First-Day Pleadings",
                "case_name": "Steward Health Care System LLC",
                "row_company_match": False,
                "docket_company_match": False,
                "docket_case_name": "Steward Health Care System LLC",
                "docket_case_name_short": "Steward",
                "docket_id": 123,
            },
        )

        self.assertFalse(result["passed"])
        self.assertEqual("rejected", result["provenance_status"])

    def test_verifier_rejects_generic_single_token_cross_case_match(self):
        verifier = VerifierAgent()
        result = verifier.verify(
            {"company_name": "Express, Inc."},
            {
                "description": "Second Interim Order Approving Use of Cash Collateral",
                "case_name": "Bamby Express, Inc.",
                "row_company_match": False,
                "docket_company_match": False,
                "docket_case_name": "Bamby Express, Inc.",
                "docket_case_name_short": "Bamby Express",
            },
        )

        self.assertFalse(result["same_case_confirmed"])
        self.assertEqual("rejected", result["provenance_status"])

    def test_verifier_accepts_search_alias_match_for_dba_case(self):
        verifier = VerifierAgent()
        result = verifier.verify(
            {"company_name": "Buca C, LLC", "search_aliases": ["Buca di Beppo"]},
            {
                "description": "Declaration of CRO in Support of Chapter 11 Petitions and First Day Motions",
                "case_name": "Buca di Beppo Holdings, LLC",
                "row_company_match": False,
                "docket_company_match": False,
                "docket_case_name": "",
                "docket_case_name_short": "",
            },
        )

        self.assertTrue(result["same_case_confirmed"])
        self.assertTrue(result["passed"])


if __name__ == "__main__":
    unittest.main()
