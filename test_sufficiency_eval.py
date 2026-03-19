import json
import tempfile
import unittest
from pathlib import Path

import sufficiency_eval


class SufficiencyEvalTests(unittest.TestCase):
    def test_resolve_local_path_handles_manifest_relative_windows_style_path(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            manifest_dir = root / "downloads" / "demo-2024"
            manifest_dir.mkdir(parents=True)
            pdf_path = manifest_dir / "01_first_day_declaration.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n")
            manifest_path = manifest_dir / "manifest.json"
            manifest_path.write_text("{}", encoding="utf-8")

            resolved = sufficiency_eval.resolve_local_path(
                manifest_path,
                "./downloads\\demo-2024\\01_first_day_declaration.pdf",
            )

        self.assertEqual(pdf_path, resolved)

    def test_extract_json_object_handles_markdown_wrapped_json(self):
        raw = """Here is the result.

```json
{"sufficient_for_v4": true, "missing_doc_type": null}
```
"""
        parsed = sufficiency_eval.extract_json_object(raw)
        self.assertEqual(True, parsed["sufficient_for_v4"])
        self.assertIsNone(parsed["missing_doc_type"])

    def test_evaluate_manifest_returns_structured_result(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            deal_dir = root / "downloads" / "conns-2024"
            deal_dir.mkdir(parents=True)
            pdf_path = deal_dir / "01_first_day_declaration.pdf"
            pdf_path.write_bytes(b"%PDF-1.4\n")
            manifest = {
                "deal_id": "conns-2024",
                "required_doc_types": ["first_day_declaration", "dip_motion"],
                "minimum_required_coverage": 2,
                "documents": [
                    {
                        "normalized_doc_type": "first_day_declaration",
                        "local_path": "./downloads\\conns-2024\\01_first_day_declaration.pdf",
                        "candidate_title": "Declaration in Support of Chapter 11 Petitions",
                        "same_case_confirmed": True,
                    }
                ],
            }
            manifest_path = deal_dir / "manifest.json"
            manifest_path.write_text(json.dumps(manifest), encoding="utf-8")

            def fake_extractor(path: Path, max_pages: int = 8, max_chars: int = 12000) -> str:
                self.assertEqual(pdf_path, path)
                return "Debtor declares chapter 11 first day facts and liquidity pressure."

            def fake_llm(prompt: str, api_key: str, model: str, base_url: str, timeout: int) -> str:
                self.assertIn("total_leverage", prompt)
                self.assertIn("first_day_declaration", prompt)
                return json.dumps(
                    {
                        "sufficient_for_v4": False,
                        "sufficient_for_critical_fields": False,
                        "missing_doc_likely_exists": True,
                        "missing_doc_type": "dip_motion",
                        "likely_missing_reason": "Financing evidence is missing from the current bundle.",
                        "critical_fields_supported": ["covenant_lite"],
                        "critical_fields_blocked": ["total_leverage", "add_backs_percent", "largest_customer_percent"],
                        "verdict": "Need financing support document.",
                        "notes": "First-day declaration alone is not enough.",
                    }
                )

            result = sufficiency_eval.evaluate_manifest(
                manifest_path=manifest_path,
                api_key="test-key",
                model="meta/llama-3.3-70b-instruct",
                base_url="https://example.com/v1",
                llm_caller=fake_llm,
                text_extractor=fake_extractor,
            )

        self.assertEqual("conns-2024", result["deal_id"])
        self.assertEqual("dip_motion", result["missing_doc_type"])
        self.assertEqual(["first_day_declaration"], result["available_doc_types"])
        self.assertFalse(result["sufficient_for_v4"])
        self.assertEqual(1, result["documents_reviewed"])

    def test_extract_pdf_text_prioritizes_targeted_pages(self):
        class FakePage:
            def __init__(self, text: str) -> None:
                self._text = text

            def extract_text(self) -> str:
                return self._text

        class FakeReader:
            def __init__(self, _: str) -> None:
                self.pages = [
                    FakePage("Intro page."),
                    FakePage("Operational overview only."),
                    FakePage("This page includes Total Leverage and EBITDA details."),
                ]

        original_reader = sufficiency_eval.PdfReader
        sufficiency_eval.PdfReader = FakeReader
        try:
            text = sufficiency_eval.extract_pdf_text(Path("dummy.pdf"), max_pages=3, max_chars=1000)
        finally:
            sufficiency_eval.PdfReader = original_reader

        self.assertIn("[Page 3]", text)
        self.assertLess(text.index("[Page 3]"), text.index("[Page 1]"))


if __name__ == "__main__":
    unittest.main()
