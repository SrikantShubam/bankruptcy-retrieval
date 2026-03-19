# ARCHITECTURE_BUNDLE_V1

This document defines the retrieval architecture used to power the v4 engine with a multi-document evidence set.

## Goal

Retrieve a small, high-signal bundle per deal instead of a single "closest" PDF.

- Retrieval mode: `coverage_bundle_v1`
- Target: required source-type coverage
- Hard cap: `4` documents per deal

## Source-Type Contract

Normalized source types:

- `credit_agreement`
- `dip_motion`
- `first_day_declaration`
- `cash_collateral_motion`
- `interim_dip_order`
- `sale_motion`
- `other_supporting`

Required coverage is resolved from:

1. `required_doc_types` on deal/truth
2. fallback to `target_doc_types`
3. fallback to best/expected source type

## Pipeline Behavior

1. Retriever returns ranked candidates.
2. Verifier and decision agent evaluate candidates and keep all `DOWNLOAD` approvals.
3. Bundle selector chooses a minimal set that satisfies required source types.
4. Fetcher downloads selected files up to cap.
5. Pipeline writes per-deal `manifest.json` with typed document metadata.
6. Telemetry scores bundle completeness and required type recall.

## Output Contract

Per deal:

- `downloads/<deal_id>/<rank>_<normalized_doc_type>.pdf`
- `downloads/<deal_id>/manifest.json`

Manifest fields include:

- `required_doc_types`
- `minimum_required_coverage`
- `required_hits`
- `bundle_complete`
- `documents[]` with rank, normalized type, source URL, local path, and selection reason

## Benchmark Semantics

Primary scoring is coverage-based:

- `TP`: bundle satisfies required coverage
- `FN`: has data but bundle missing required coverage
- `FP`: downloaded bundle for a true negative
- `TN`: correctly skipped/not found for true negative

Key bundle metrics:

- `bundle_complete_deals`
- `bundle_partial_deals`
- `bundle_complete_rate`
- `required_doc_type_recall`
- `selected_documents_total`
