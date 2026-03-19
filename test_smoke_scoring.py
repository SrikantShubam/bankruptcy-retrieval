import unittest

from shared.telemetry import TelemetryCollector


class SmokeScoringTests(unittest.TestCase):
    def test_incomplete_bundle_is_scored_as_false_negative(self):
        telemetry = TelemetryCollector()
        telemetry.record_terminal(
            {
                "deal_id": "exactech-2024",
                "pipeline_status": "DOWNLOADED",
                "selected_doc_types": ["first_day_declaration"],
            }
        )

        report = telemetry.summarize(
            ground_truth={
                "exactech-2024": {
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
        self.assertEqual(1, report["doc_type_mismatch_downloads"])

    def test_complete_bundle_is_scored_as_true_positive(self):
        telemetry = TelemetryCollector()
        telemetry.record_terminal(
            {
                "deal_id": "conns-2024",
                "pipeline_status": "DOWNLOADED",
                "selected_doc_types": ["dip_motion", "first_day_declaration"],
            }
        )

        report = telemetry.summarize(
            ground_truth={
                "conns-2024": {
                    "has_financial_data": True,
                    "already_processed": False,
                    "required_doc_types": ["dip_motion", "first_day_declaration"],
                    "minimum_required_coverage": 2,
                }
            },
            total_api_calls=1,
            total_llm_calls=0,
        )

        self.assertEqual(1, report["TP"])
        self.assertEqual(0, report["FN"])
        self.assertEqual(0, report["doc_type_mismatch_downloads"])


if __name__ == "__main__":
    unittest.main()
