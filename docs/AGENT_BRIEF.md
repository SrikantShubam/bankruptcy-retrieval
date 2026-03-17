# Worktree D Agent Brief

## Mission
Implement Worktree D as an agent-first retrieval pipeline for Chapter 11 first-day/DIP documents.

## Scope
- Work only in Worktree D code and docs.
- Do not alter logic in Worktrees A/B/C.

## Data and File Access
- Dataset: `data/deals_dataset.json`
- Ground truth: `data/ground_truth.json`
- Existing C references:
  - graph orchestration: `graph.py`
  - node behavior: `nodes.py`
  - telemetry implementation: `shared/telemetry.py`
  - run entrypoint: `main.py`
- Output logs:
  - `logs/execution_log.jsonl`
  - `logs/benchmark_report.json`

## Runtime/Control Constraints
- CourtListener is primary source.
- Handle connectivity failures explicitly as `INFRA_FAILED`.
- Keep API usage bounded with adaptive stopping.
- Avoid repeated identical retries.
- Download only after positive decision.

## Acceptance Criteria
1. 10-case smoke run completes with `infra_failed=0` (when network is healthy).
2. Full run completes with benchmark report generated.
3. Report includes metric comparison vs Worktree C baseline and exact FN/FP deal IDs.

