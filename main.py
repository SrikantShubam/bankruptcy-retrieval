import argparse
import os
from typing import Any, Dict, List

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
            }

    return out


def main() -> None:
    _load_dotenv()

    parser = argparse.ArgumentParser(description="Worktree D agent-first retrieval pipeline")
    parser.add_argument("--standard-test", action="store_true", help="Run the standard 10-deal benchmark subset")
    args = parser.parse_args()

    deals: List[dict] = load_json("data/deals_dataset.json", default=[])
    ground_truth = _normalize_ground_truth(load_json("data/ground_truth.json", default={}))

    if args.standard_test:
        deal_map = {d.get("deal_id"): d for d in deals}
        deals = [deal_map[d] for d in STANDARD_TEST_DEALS if d in deal_map]

    if not deals:
        print("No deals found at data/deals_dataset.json")
        print("Expected files: data/deals_dataset.json and data/ground_truth.json")
        return

    report = run_pipeline(deals=deals, ground_truth=ground_truth)
    print("Run complete")
    print(report)


if __name__ == "__main__":
    main()
