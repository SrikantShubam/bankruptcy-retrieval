# Worktree D Architecture

## Goal
Build an agent-first retrieval system that improves recall on hard positives while keeping false positives low.

## Proposed Flow
1. `Planner Agent`
   - Builds staged query plans from deal metadata.
   - Produces strict-first then broadened fallback query variants.
2. `Retriever Agent`
   - Executes plan against CourtListener (`type=rd` primary, controlled `type=r` fallback).
   - Returns normalized candidate records.
3. `Verifier Agent`
   - Confirms company/court alignment from metadata and docket checks.
   - Applies deterministic reject rules for obvious non-target filings.
4. `Decision Agent`
   - Decides `DOWNLOAD`, `SKIP`, or `RETRY_QUERY`.
   - Uses confidence + budget-aware stopping.
5. `Fetcher`
   - Downloads approved candidate only.
6. `Telemetry`
   - Logs terminal status and benchmark metrics.

## Design Rules
- Keep A/B/C untouched; D must be isolated.
- No blind downloads before verification.
- Retry only with a changed query strategy.
- Decoys should fail closed by default.

