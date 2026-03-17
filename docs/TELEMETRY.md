# Worktree D Telemetry Contract

## Required Metrics
- `TP`, `FP`, `FN`, `TN`
- `precision`, `recall`, `f1_score`
- `infra_failed`
- `total_api_calls`
- `total_llm_gatekeeper_calls` (or equivalent decision calls)
- `total_runtime_seconds`
- `deals_total`, `deals_active`, `deals_already_processed`

## Terminal Statuses
Use consistent terminal statuses:
- `DOWNLOADED`
- `NOT_FOUND`
- `SKIPPED`
- `FETCH_FAILED`
- `INFRA_FAILED`
- `ALREADY_PROCESSED`

## Logging Requirements
- One terminal event per deal.
- Include `deal_id`, `pipeline_status`, API call count, runtime, and downloaded file path if present.
- Keep output compatible with benchmark summary generation used in Worktree C.

## Evaluation Protocol
1. Run 10-case smoke benchmark.
2. Run full benchmark.
3. Report both headline metrics and exact `FP/FN` deal IDs.

