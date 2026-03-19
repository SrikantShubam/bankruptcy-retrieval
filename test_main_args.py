import json
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import main


class MainArgTests(unittest.TestCase):
    def test_priority1_hard_uses_hard_dataset_paths(self):
        deals = [{"deal_id": "hard-case-1"}]
        truth = {"hard-case-1": {"has_financial_data": True, "already_processed": False}}
        with patch("main.run_pipeline", return_value={"ok": True}) as run_pipeline:
            with patch("sys.argv", ["main.py", "--priority1-hard"]):
                with tempfile.TemporaryDirectory() as tmp:
                    data_dir = Path(tmp)
                    (data_dir / "priority1_hard_cases.json").write_text(json.dumps(deals), encoding="utf-8")
                    (data_dir / "priority1_hard_ground_truth.json").write_text(json.dumps(truth), encoding="utf-8")
                    with patch.object(main, "load_json", side_effect=[deals, truth]):
                        main.main(data_dir=data_dir)

        self.assertTrue(run_pipeline.called)
        self.assertEqual(deals, run_pipeline.call_args.kwargs["deals"])

    def test_dataset_and_ground_truth_overrides_are_used(self):
        deals = [{"deal_id": "demo"}]
        truth = {"demo": {"has_financial_data": True, "already_processed": False}}

        with patch("main.run_pipeline", return_value={"ok": True}) as run_pipeline:
            with patch("sys.argv", ["main.py", "--dataset", "custom_deals.json", "--ground-truth", "custom_truth.json"]):
                with tempfile.TemporaryDirectory() as tmp:
                    data_dir = Path(tmp)
                    with patch.object(main, "load_json", side_effect=[deals, truth]):
                        main.main(data_dir=data_dir)

        self.assertEqual(deals, run_pipeline.call_args.kwargs["deals"])
        self.assertEqual(
            {
                "demo": {
                    "has_financial_data": True,
                    "already_processed": False,
                    "expected_doc_type": None,
                    "expected_best_source_doc_type": None,
                    "required_doc_types": None,
                    "minimum_required_coverage": None,
                }
            },
            run_pipeline.call_args.kwargs["ground_truth"],
        )


if __name__ == "__main__":
    unittest.main()
