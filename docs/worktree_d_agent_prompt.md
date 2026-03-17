# Worktree D Kickoff Prompt (Agent-First Approach)

You are implementing **Worktree D** for the `bankruptcy-retrieval` repo.

## Mission
Build an **agent-driven retrieval pipeline** that improves recall on the known hard FN set while keeping FP tightly controlled on decoys/non-targets.  
Use CourtListener as primary source, but let the agent perform iterative query planning and evidence validation before final download decisions.

## Hard Requirements
1. Do **not** modify Worktrees A/B/C behavior. Work only in Worktree D files.
2. Keep the same benchmark dataset and ground truth used by Worktree C.
3. Keep telemetry compatible with existing benchmark outputs (`TP/FP/FN/TN`, `F1`, `infra_failed`, runtime, API calls).
4. If network fails, classify as infra failure instead of mixing with retrieval quality.
5. Ensure deterministic/reproducible runs with fixed control flow where possible.

## Baseline to Beat
- Current Worktree C full run baseline: `F1 ~0.84` with nonzero FN and some FP.
- Key recurring FN cluster includes:
  - `bed-bath-beyond-2023`
  - `mallinckrodt-2023`
  - `icon-aircraft-2023`
  - `ligado-networks-2024`
  - `lannett-2023`
  - `chicken-soup-2023`
  - `core-scientific-2022`
  - `rackspace-2023`
  - plus occasional DIP/first-day misses
- Key FP risk includes non-target entities and ambiguous name collisions.

## Proposed Agent Design (Implement This)
1. **Planner Agent**
   - Input: deal metadata (`deal_id`, company name, filing year, court, expected type unknown).
   - Output: ranked query plan with staged variants:
     - strict company + first-day terms
     - DIP/cash-collateral terms
     - chapter-11 + debtor declaration terms
     - fallback normalized company name variants
2. **Retriever Agent**
   - Executes query plan against CourtListener (`type=rd` first, then controlled `type=r` fallback).
   - Captures candidate metadata only (no blind download).
   - Deduplicates by URL/docket entry.
3. **Verifier Agent**
   - Validates company/court alignment using docket metadata when ambiguous.
   - Scores evidence confidence from title semantics.
   - Rejects noisy categories (routine orders, fee apps, service certs, summary judgment, etc.).
4. **Decision Agent**
   - Chooses `DOWNLOAD`, `SKIP`, or `RETRY_QUERY`.
   - Allows retry only with explicit rationale and remaining budget.
5. **Fetcher**
   - Download only after verified decision.

## Efficiency/Budget Constraints
1. Keep per-deal API budget bounded (target similar or slightly above Worktree C).
2. Add adaptive stopping:
   - stop early on high-confidence verified hit
   - continue broader search only when confidence is low
3. Avoid repeated identical queries across retries.

## Evaluation Protocol
1. Run a 10-case smoke set first (same standard test concept as C).
2. Then run full benchmark.
3. Report:
   - metrics (`F1`, `P`, `R`, `TP/FP/FN/TN`, `infra_failed`)
   - list of FN and FP deal IDs
   - API call totals and runtime
4. Compare directly against Worktree C baseline.

## Implementation Notes
1. Prefer modular code:
   - `agents/planner.py`
   - `agents/retriever.py`
   - `agents/verifier.py`
   - `agents/decision.py`
   - orchestrator in `main.py`/`graph.py` equivalent for D
2. Keep prompts small, explicit, and schema-bound.
3. Favor deterministic heuristics for final safety checks even when using LLM reasoning.
4. Add debug traces to explain why each FN/FP occurred.

## Deliverables
1. Working Worktree D pipeline code.
2. Updated docs describing D architecture.
3. Benchmark report JSON and concise summary with A/B/C/D comparison.

