# Worktree D Runtime

## Required env vars
- `COURTLISTENER_API_TOKEN`
- `OPENROUTER_API_KEY`

## Commands
- Smoke: `python main.py --standard-test`
- Full: `python main.py`

## Notes
- Uses CourtListener search API (`type=rd` primary, `type=r` fallback).
- Uses `openrouter/hunter-alpha` for decision gating when key is present.
- Produces:
  - `logs/execution_log.jsonl`
  - `logs/benchmark_report.json`
