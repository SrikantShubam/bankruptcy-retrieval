import argparse
import os
from typing import Any, Dict, List
from pathlib import Path

from graph import load_json, run_pipeline


STANDARD_TEST_DEALS = [
    "wework-2023",
    "rite-aid-2023",
    "blockfi-2022",
    "bed-bath-beyond-2023",
    "yellow-corp-2023",
    "mitchells-butlers-2023",
    "kidoz-2023",
    "svb-financial-2023",
    "talen-energy-2023",
    "medical-decoy-c",
]


def _load_dotenv(path: str = ".env") -> None:
    if not os.path.exists(path):
        return

    with open(path, "r", encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, val = line.split("=", 1)
            key = key.strip()
            val = val.strip().strip('"').strip("'")
            if key and key not in os.environ:
                os.environ[key] = val


def _normalize_ground_truth(raw: object) -> Dict[str, Dict[str, Any]]:
    out: Dict[str, Dict[str, Any]] = {}

    if isinstance(raw, dict):
        for deal_id, v in raw.items():
            if isinstance(v, dict):
                out[str(deal_id)] = {
                    "has_financial_data": bool(v.get("has_financial_data", False)),
                    "already_processed": bool(v.get("already_processed", False)),
                    "expected_doc_type": v.get("expected_doc_type"),
                    "expected_best_source_doc_type": v.get("expected_best_source_doc_type"),
                    "required_doc_types": v.get("required_doc_types"),
                    "minimum_required_coverage": v.get("minimum_required_coverage"),
                }
            else:
                out[str(deal_id)] = {
                    "has_financial_data": bool(v),
                    "already_processed": False,
                }
        return out

    if isinstance(raw, list):
        for row in raw:
            if not isinstance(row, dict):
                continue
            deal_id = row.get("deal_id") or row.get("id")
            if not deal_id:
                continue
            out[str(deal_id)] = {
                "has_financial_data": bool(row.get("has_financial_data", row.get("is_positive", row.get("positive", False)))),
                "already_processed": bool(row.get("already_processed", False)),
                "expected_doc_type": row.get("expected_doc_type"),
                "expected_best_source_doc_type": row.get("expected_best_source_doc_type"),
                "required_doc_types": row.get("required_doc_types"),
                "minimum_required_coverage": row.get("minimum_required_coverage"),
            }

    return out


def _resolve_paths(args: argparse.Namespace, data_dir: Path) -> tuple[Path, Path]:
    if args.priority1_hard:
        dataset = data_dir / "priority1_hard_cases.json"
        ground_truth = data_dir / "priority1_hard_ground_truth.json"
    else:
        dataset = Path(args.dataset) if args.dataset else data_dir / "deals_dataset.json"
        ground_truth = Path(args.ground_truth) if args.ground_truth else data_dir / "ground_truth.json"
    return dataset, ground_truth


def main(data_dir: Path | None = None) -> None:
    _load_dotenv()
    data_dir = data_dir or (Path(__file__).parent / "data")

    parser = argparse.ArgumentParser(description="Worktree D agent-first retrieval pipeline")
    parser.add_argument("--standard-test", action="store_true", help="Run the standard 10-deal benchmark subset")
    parser.add_argument("--priority1-hard", action="store_true", help="Run the 11-case Priority 1 hard smoke set")
    parser.add_argument("--dataset", help="Path to an alternate deals dataset JSON")
    parser.add_argument("--ground-truth", help="Path to an alternate ground truth JSON")
    args = parser.parse_args()

    dataset_path, ground_truth_path = _resolve_paths(args, data_dir)

    deals: List[dict] = load_json(str(dataset_path), default=[])
    ground_truth = _normalize_ground_truth(load_json(str(ground_truth_path), default={}))

    if args.standard_test:
        deal_map = {d.get("deal_id"): d for d in deals}
        deals = [deal_map[d] for d in STANDARD_TEST_DEALS if d in deal_map]

    if not deals:
        print(f"No deals found at {dataset_path}")
        print(f"Expected files: {dataset_path} and {ground_truth_path}")
        return

    report = run_pipeline(deals=deals, ground_truth=ground_truth)
    print("Run complete")
    print(report)


if __name__ == "__main__":
    main()
