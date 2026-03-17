# Worktree D GitHub Repo Requirements

## Branch And Worktree Convention
1. Create a dedicated branch for D:
   - `worktree-d-agentic`
2. Create a dedicated git worktree directory:
   - example: `C:\experiments\worktree-d`
3. Keep D commits isolated; do not mix with A/B/C branches.

## Required Repository Layout For D
1. `main.py` (or `main_d.py`) as D entrypoint.
2. `graph.py` (or `graph_d.py`) for agent orchestration.
3. `agents/` package with at least:
   - `planner.py`
   - `retriever.py`
   - `verifier.py`
   - `decision.py`
4. `shared/telemetry.py` compatibility preserved (or adapter layer).
5. `logs/` output compatibility:
   - `execution_log.jsonl`
   - `benchmark_report.json`
6. `docs/worktree_d/` retained and updated as implementation evolves.

## Config And Environment
1. `.env` keys required:
   - `COURTLISTENER_API_TOKEN`
   - `OPENROUTER_API_KEY` and/or `NVIDIA_NIM_API_KEY`
2. No hardcoded secrets in code or docs.
3. Add `.env` to `.gitignore` (if not already).

## Dependency And Runtime Rules
1. Keep dependencies pinned in `requirements.txt`.
2. If new packages are needed for D, document why in commit/PR message.
3. Ensure commands run from repo root:
   - `python main.py --standard-test`
   - `python main.py`

## CI / Verification Minimum
1. Lint/type checks if available.
2. At minimum, run and report:
   - syntax check (`py_compile` or equivalent)
   - 10-case smoke benchmark
   - full benchmark
3. Fail the PR if:
   - benchmark report not generated
   - terminal statuses are inconsistent
   - infra failures are mixed into retrieval metrics

## Telemetry Contract (Must Keep)
1. Preserve metric fields:
   - `TP`, `FP`, `FN`, `TN`, `precision`, `recall`, `f1_score`
   - `infra_failed`, `total_api_calls`, `total_runtime_seconds`
2. Preserve terminal statuses:
   - `DOWNLOADED`, `NOT_FOUND`, `SKIPPED`, `FETCH_FAILED`, `INFRA_FAILED`, `ALREADY_PROCESSED`
3. Ensure one terminal record per processed deal.

## PR Checklist For Worktree D
1. Architecture doc updated.
2. Telemetry doc updated.
3. Agent brief updated with any changed interfaces.
4. Smoke + full benchmark results pasted in PR description.
5. FP/FN deal IDs listed explicitly.
6. Comparison vs current Worktree C baseline included.

## Suggested Commit Sequence
1. `feat(d): scaffold agent modules and graph`
2. `feat(d): add planner/retriever first-pass retrieval`
3. `feat(d): add verifier+decision with strict telemetry compatibility`
4. `test(d): run smoke benchmark and record metrics`
5. `perf(d): iterate on FN/FP with evidence-backed tuning`
6. `chore(d): final full benchmark report and docs sync`

