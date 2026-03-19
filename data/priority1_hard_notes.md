# Priority 1 Hard Set

Purpose:
- `priority1_hard` is the full 11-case exact-best-source stress set used to pressure-test retrieval changes.
- `expected_doc_type` remains compatible with the existing benchmark shape.
- `expected_best_source_doc_type` is the strict scoring field for this smoke benchmark.

Active cases:
- `express-2024`
- `rue21-2024`
- `steward-health-2024`
- `fisker-2024`
- `tgi-fridays-2024`
- `hornblower-2024`
- `conns-2024`
- `ll-flooring-2024`
- `buca-di-beppo-2024`
- `exactech-2024`
- `caremax-2024`

Interpretation:
- This is a harder stress set than the cleaned 5-case CourtListener-confirmed subset.
- Some cases are known to have weaker CourtListener truth for exact-best-source benchmarking, but they are intentionally included here to keep pressure on source selection.
- The archive files are retained as reference snapshots from the earlier 5-case split and are not used by the runner.
