# Auditor Handoff

This file is the single handoff for an external auditor reviewing the current state of `worktree_d_git`, the methods already tried, the failures encountered, and the current open problems.

## Goal

Build a retrieval system that gathers bankruptcy documents good enough to power the `v4` engine in `C:\experiments\ag dead deal autopsy\v4`.

The key realization is that the engine does not care about retrieval benchmark purity by itself. It cares whether the downloaded document set is actually sufficient to support extraction of the financial / capital-structure facts that `v4` wants.

## Core Repos and Files

### D branch under active work

- [main.py](/C:/experiments/worktree_d_git/main.py)
- [graph.py](/C:/experiments/worktree_d_git/graph.py)
- [agents/planner.py](/C:/experiments/worktree_d_git/agents/planner.py)
- [agents/retriever.py](/C:/experiments/worktree_d_git/agents/retriever.py)
- [agents/verifier.py](/C:/experiments/worktree_d_git/agents/verifier.py)
- [agents/decision.py](/C:/experiments/worktree_d_git/agents/decision.py)
- [shared/telemetry.py](/C:/experiments/worktree_d_git/shared/telemetry.py)
- [sufficiency_eval.py](/C:/experiments/worktree_d_git/sufficiency_eval.py)

### D reports and artifacts

- [benchmark_report.json](/C:/experiments/worktree_d_git/logs/benchmark_report.json)
- [v4_sufficiency_report.json](/C:/experiments/worktree_d_git/logs/v4_sufficiency_report.json)
- [execution_log.jsonl](/C:/experiments/worktree_d_git/logs/execution_log.jsonl)
- [downloads](/C:/experiments/worktree_d_git/downloads)

### D tests

- [test_retriever_retries.py](/C:/experiments/worktree_d_git/test_retriever_retries.py)
- [test_d_provenance.py](/C:/experiments/worktree_d_git/test_d_provenance.py)
- [test_planner_hard_cases.py](/C:/experiments/worktree_d_git/test_planner_hard_cases.py)
- [test_smoke_scoring.py](/C:/experiments/worktree_d_git/test_smoke_scoring.py)
- [test_sufficiency_eval.py](/C:/experiments/worktree_d_git/test_sufficiency_eval.py)

### Shared benchmark truth

- [priority1_hard_cases.json](/C:/experiments/worktree_d_git/data/priority1_hard_cases.json)
- [priority1_hard_ground_truth.json](/C:/experiments/worktree_d_git/data/priority1_hard_ground_truth.json)

### Reference engine

- [config.py](/C:/experiments/ag dead deal autopsy/v4/config.py)
- [master.py](/C:/experiments/ag dead deal autopsy/v4/master.py)
- [v2_master.py](/C:/experiments/ag dead deal autopsy/v4/v2_master.py)
- [journey.md](/C:/experiments/ag dead deal autopsy/v4/journey.md)

## Current Bottom Line

Under the current strict 11-case hard benchmark:

- TP `3`
- FP `0`
- FN `8`
- Precision `1.0`
- Recall `0.2727`
- F1 `0.4286`
- Bundle complete deals `3`
- Required doc-type recall `0.4545`

Source: [benchmark_report.json](/C:/experiments/worktree_d_git/logs/benchmark_report.json)

Under the new `v4` sufficiency evaluator:

- Deals evaluable from actual manifests: `9`
- Sufficient for `v4`: `0/9`
- Sufficient for critical fields: `0/9`
- Missing another important document likely exists: `9/9`

Source: [v4_sufficiency_report.json](/C:/experiments/worktree_d_git/logs/v4_sufficiency_report.json)

This means the current D system is still not producing document bundles that look usable for `v4`, even when the raw retrieval benchmark suggests some success.

## Important Context From V4

`v4` is fundamentally multi-document oriented. It expects a useful deal corpus, not a single “best PDF”.

Important points:

- `v4` tracks critical fields in [config.py](/C:/experiments/ag dead deal autopsy/v4/config.py):
  - `total_leverage`
  - `add_backs_percent`
  - `covenant_lite`
  - `largest_customer_percent`
- `master.py` and `v2_master.py` both work around multi-document `docs` / `doc_map` style inputs.
- The engine often needs several PDFs together, not one winner.

This matters because much of the earlier retrieval work was benchmarked as if selecting one exact best file was the main problem.

## What Was Tried

### 1. D cleanup and branch stabilization

The duplicate `d` worktree situation was resolved earlier. The real D branch is `C:\experiments\worktree_d_git`.

### 2. CourtListener infra resilience

Problem:

- D had transient `HTTP 502` failures that aborted deals.

Change made:

- added retry/backoff for transient `429/502/503/504`, `URLError`, and timeouts in [agents/retriever.py](/C:/experiments/worktree_d_git/agents/retriever.py)
- query-variant failures no longer abort the whole deal

Result:

- infra failures dropped to `0`
- this fixed stability, but not bundle depth

Tests:

- [test_retriever_retries.py](/C:/experiments/worktree_d_git/test_retriever_retries.py)

### 3. D converted from single-winner retrieval to bundle retrieval

Problem:

- the engine needs a document set, not one closest file

Changes made:

- D now writes per-deal manifests in [graph.py](/C:/experiments/worktree_d_git/graph.py)
- bundle output contract includes typed documents and bundle completeness metadata
- cap is `4` selected files per deal

Result:

- system now downloads bundles and writes `manifest.json`
- this improved architecture clarity, but did not solve missing financing docs

### 4. Provenance hardening

Problem:

- D was getting fake wins from wrong-case documents

Observed contamination examples before hardening:

- `rue21-2024` got a `dip_motion` from `Careismatic Brands`
- `ll-flooring-2024` got a `dip_motion` from `ICON Aircraft`
- `express-2024` got a `cash_collateral_motion` from `Bamby Express`
- `caremax-2024` got a `first_day_declaration` from `Steward Health`

Changes made:

- generic-name matching tightened
- wrong-case docs no longer count toward bundle success
- generic first-day motions no longer normalize as `first_day_declaration`
- provenance metadata added to selected docs

Key files:

- [agents/verifier.py](/C:/experiments/worktree_d_git/agents/verifier.py)
- [agents/retriever.py](/C:/experiments/worktree_d_git/agents/retriever.py)
- [graph.py](/C:/experiments/worktree_d_git/graph.py)
- [shared/telemetry.py](/C:/experiments/worktree_d_git/shared/telemetry.py)

Tests:

- [test_d_provenance.py](/C:/experiments/worktree_d_git/test_d_provenance.py)

Result:

- truthful score dropped when contamination was removed
- later recall fixes recovered some score
- current score is more honest, but still poor

### 5. 11-case hard smoke set

Purpose:

- stress D on real hard cases without decoys

Result:

- D could avoid junk, but often failed to get the needed document bundle
- most misses were incomplete bundles, not random bad downloads

### 6. Manual miss validation against CourtListener

A manual validation pass was done to determine whether the misses were true retrieval failures or source-availability problems.

High-level findings:

- `express-2024`: same-case DIP exists; same-case first-day did not surface cleanly
- `rue21-2024`: same-case first-day and cash collateral exist; same-case DIP did not surface cleanly
- `ll-flooring-2024`: same-case first-day exists; no same-case DIP found
- `exactech-2024`: same-case first-day exists; no same-case DIP found
- `fisker-2024`: only wrong-case material surfaced
- `tgi-fridays-2024`: no candidates surfaced
- `caremax-2024`: only wrong-case material surfaced
- `buca-di-beppo-2024`: no candidates surfaced

Interpretation:

- some misses are real D misses
- several look like CourtListener-availability limits
- not all misses can be fixed by tuning query logic alone

### 7. V4 sufficiency evaluator

Reason:

- F1 was not answering the actual question: are the downloaded docs enough for the engine?

Implementation:

- [sufficiency_eval.py](/C:/experiments/worktree_d_git/sufficiency_eval.py)
- [test_sufficiency_eval.py](/C:/experiments/worktree_d_git/test_sufficiency_eval.py)

The evaluator:

- reads each D `manifest.json`
- extracts PDF text snippets
- sends the bundle to NVIDIA using the existing local `v4` configuration
- asks whether the bundle is enough for a `v4`-style task
- asks whether another important file likely exists

Current result:

- `0/9` sufficient for `v4`
- `0/9` sufficient for critical fields
- `9/9` likely missing another important file

### 8. Follow-up query families for missing doc types

Problem:

- D often got one useful doc but missed the second or third file needed for the bundle

Changes made:

- added follow-up query families for missing:
  - `dip_motion`
  - `first_day_declaration`
  - `credit_agreement`
  - `cash_collateral_motion`
- graph reruns targeted retrieval when required doc types are still missing

Files:

- [agents/planner.py](/C:/experiments/worktree_d_git/agents/planner.py)
- [graph.py](/C:/experiments/worktree_d_git/graph.py)

Tests:

- [test_planner_hard_cases.py](/C:/experiments/worktree_d_git/test_planner_hard_cases.py)

Result:

- no meaningful movement in the strict benchmark
- no movement in `v4` sufficiency

## Current Problems

### 1. D is still not collecting deep enough bundles

Symptoms:

- only `13` selected documents across `11` deals
- only `3` complete bundles
- only `9` manifests available for `v4` sufficiency review

### 2. CourtListener looks like the main ceiling now

The current evidence suggests:

- provenance is cleaner
- infra is cleaner
- but same-case financing docs still do not surface often enough

This points more toward source coverage limits than obvious logic bugs.

### 3. Candidate ranking and cap logic may still suppress recall

An external reviewer noted:

- retrieval returns top `12`
- merged candidates are trimmed to `18`
- classification only inspects the first `12`

So follow-up queries may find useful docs but still lose out before bundle selection.

Relevant code:

- [agents/retriever.py](/C:/experiments/worktree_d_git/agents/retriever.py)
- [graph.py](/C:/experiments/worktree_d_git/graph.py)

### 4. The decision layer is basically not helping

Current report:

- `total_llm_gatekeeper_calls: 0`

Interpretation:

- D is mostly a heuristic retriever plus verifier
- the “agentic” label is not currently producing meaningful selector intelligence in the final path

### 5. V4 sufficiency evaluator may be too strict

An external reviewer noted the current evaluator may also be harsh because:

- it only sends the first `8` pages / `12,000` chars per PDF
- it strongly penalizes missing financing docs

That does not change the bigger problem, but it means `0/9 sufficient` may be slightly harsher than a full-document ingestion review would be.

The relevant code is in [sufficiency_eval.py](/C:/experiments/worktree_d_git/sufficiency_eval.py).

## External Reviewer Finding Already Captured

One external review was already completed before audit cancellation. The most useful conclusions were:

1. The `v4` sufficiency evaluator may be stricter than the data it actually inspects.
2. D is still rank-capped in a way that can suppress bundle completion.
3. The plateau now looks like a source-coverage problem more than a provenance problem.
4. The decision layer is not contributing meaningful selection intelligence.
5. Download quality no longer looks like the main blocker.

That reviewer’s highest-ROI next move was:

- add a narrow fallback source layer inside D for partial or empty bundles
- keep the same provenance rules and manifest contract

## What Was Not Pursued Further

### Worktree C

C was investigated but is no longer the main investment target.

It fell badly on the bundle-based and `v4`-relevance standards, and D remained clearly stronger.

### Worktree B as the main system

B already showed that browser / claims-agent scraping can help coverage, but it also showed:

- much slower runtime
- more operational brittleness
- browser/session overhead

Conclusion so far:

- browser-first is not the right backbone
- but a narrow fallback layer from B may still be useful

## Verification Performed

Tests that passed on the current D state:

- `python -m unittest test_smoke_scoring.py test_planner_hard_cases.py test_retriever_retries.py test_main_args.py test_d_provenance.py test_sufficiency_eval.py -v`

Live commands run:

- `python main.py --priority1-hard`
- `python sufficiency_eval.py`

## Auditor Questions

The auditor should answer these concretely:

1. Is the current plateau mainly caused by:
   - source coverage limits from CourtListener
   - candidate cap / ranking logic
   - overly strict `v4` sufficiency evaluation
   - or some combination

2. Is D worth more CourtListener-only tuning, or is that now low ROI?

3. Should the next change be:
   - fallback claims-agent retrieval inside D
   - a better scoring / sufficiency contract
   - a different bundle assembly strategy
   - or all three in a specific order

4. If claims-agent fallback is the next move, what is the minimum safe version that:
   - helps coverage
   - does not reintroduce B’s brittleness
   - preserves D’s provenance and manifest structure

5. Is the current `v4` sufficiency evaluator fair enough, or should it be revised before it is used as the main gate?

## Current Recommendation From This Handoff

The strongest current hypothesis is:

- D is no longer failing primarily because of contamination or infra
- D is failing because CourtListener alone is not yielding a deep enough same-case financing corpus

Therefore the highest-ROI next move appears to be:

- keep D as the core system
- add a narrow fallback source layer for partial / empty bundles
- preserve provenance hardening
- keep using the `v4` sufficiency report as a gate, but likely revise its prompt / document depth after audit

## Post-Auditor Implementation Update

After reading [auditor_report.md](/C:/experiments/worktree_d_git/docs/auditor_report.md), the following changes were implemented.

### Changes made

#### 1. Raised candidate caps

Implemented in:

- [graph.py](/C:/experiments/worktree_d_git/graph.py)
- [agents/retriever.py](/C:/experiments/worktree_d_git/agents/retriever.py)

Specific changes:

- merged candidate cap raised from `18` to `30`
- classification inspection cap raised from `12` to `24`
- retriever return / docket-verify candidate cap raised from `12` to `20`
- bundle candidate preselection widened before final bundle assembly

#### 2. Increased CourtListener call budget

Implemented in:

- [graph.py](/C:/experiments/worktree_d_git/graph.py)

Specific change:

- `RetrieverAgent(max_calls_per_deal=18)` instead of `12`

#### 3. Revised sufficiency evaluator depth

Implemented in:

- [sufficiency_eval.py](/C:/experiments/worktree_d_git/sufficiency_eval.py)

Specific changes:

- PDF extraction depth increased from `8` pages / `12,000` chars to `30` pages / `40,000` chars
- added targeted page prioritization for terms like:
  - `total leverage`
  - `EBITDA`
  - `covenant`
  - `DIP Facility`
  - `credit agreement`
  - `cash collateral`

#### 4. Added regression coverage

Implemented in:

- [test_sufficiency_eval.py](/C:/experiments/worktree_d_git/test_sufficiency_eval.py)

New coverage:

- targeted pages are prioritized ahead of generic earlier pages during PDF text extraction

### Verification run

Passed:

- `python -m unittest test_smoke_scoring.py test_planner_hard_cases.py test_retriever_retries.py test_main_args.py test_d_provenance.py test_sufficiency_eval.py -v`

### Post-change live results

#### Hard benchmark

Source: [benchmark_report.json](/C:/experiments/worktree_d_git/logs/benchmark_report.json)

- TP `3`
- FP `0`
- FN `8`
- Precision `1.0`
- Recall `0.2727`
- F1 `0.4286`
- Required doc-type recall `0.4545`
- Total API calls increased to `228`

Interpretation:

- the quick-win cap changes did not move the strict benchmark outcome
- they increased search effort, but not enough to recover additional hard cases on CourtListener alone

#### V4 sufficiency

Source: [v4_sufficiency_report.json](/C:/experiments/worktree_d_git/logs/v4_sufficiency_report.json)

- Deals evaluable: `9`
- Sufficient for `v4`: `0/9`
- Sufficient for critical fields: `1/9`
- Missing another important document likely exists: `9/9`

Important change:

- previously critical-field sufficiency was `0/9`
- after the evaluator-depth change it improved to `1/9`
- the one improved case is `hornblower-2024`, where the evaluator now sees support for:
  - `total_leverage`
  - `add_backs_percent`
  - `covenant_lite`

Interpretation:

- the auditor was correct that the prior sufficiency evaluator was too shallow
- deeper extraction made the evaluator more informative
- but it still does not change the main conclusion: D is not yet producing `v4`-ready bundles at scale

### Updated current view

After implementing the auditor’s P0/P1 quick wins:

- the evaluator is somewhat fairer
- the retrieval caps are less restrictive
- but the practical ceiling still appears to be source coverage, not just local pipeline mechanics

So the next meaningful improvement is still likely:

- a narrow fallback source layer for partial / empty bundles

## Plateau-Break Attempt: Docket-First and Alias Expansion

A second implementation pass targeted the hypothesis that the `0.4286` plateau was not purely a source ceiling, but also a retrieval-strategy problem.

### Changes made

#### 1. Planner: docket variants and broader alias expansion

Implemented in:

- [agents/planner.py](/C:/experiments/worktree_d_git/agents/planner.py)

Changes:

- added broader alias expansion via `_expand_alias_variants`
- added `build_docket_variants(deal)` to generate:
  - `type=d` docket queries
  - alias-based docket searches
  - year-bounded and yearless docket queries
- this specifically covers DBA / subsidiary naming cases like:
  - `Buca C, LLC` vs `Buca di Beppo`

#### 2. Retriever: honor yearless / non-available-only variants

Implemented in:

- [agents/retriever.py](/C:/experiments/worktree_d_git/agents/retriever.py)

Changes:

- `execute_plan()` now honors per-variant `available_only`
- `execute_docket_plan()` now accepts explicit docket variants from the planner
- docket search breadth increased:
  - more docket search variants
  - more dockets fetched
- docket candidates now use alias-aware company matching consistently

#### 3. Graph: trigger docket fallback on weak coverage, not just total failure

Implemented in:

- [graph.py](/C:/experiments/worktree_d_git/graph.py)

Changes:

- docket-first fallback now triggers when the deal has `<= 1` same-case confirmed candidate
- this runs:
  - after initial classification
  - and again after follow-up query expansion if coverage is still weak

#### 4. Added tests for the new retrieval path

Implemented in:

- [test_planner_hard_cases.py](/C:/experiments/worktree_d_git/test_planner_hard_cases.py)
- [test_d_provenance.py](/C:/experiments/worktree_d_git/test_d_provenance.py)

New test coverage:

- docket variants include alias and yearless search
- verifier accepts same-case alias matches for DBA-style cases

### Verification run

Passed:

- `python -m unittest test_smoke_scoring.py test_planner_hard_cases.py test_retriever_retries.py test_main_args.py test_d_provenance.py test_sufficiency_eval.py -v`

### Post-change live results

#### Hard benchmark

Source: [benchmark_report.json](/C:/experiments/worktree_d_git/logs/benchmark_report.json)

- TP `3`
- FP `0`
- FN `8`
- Precision `1.0`
- Recall `0.2727`
- F1 `0.4286`
- Bundle partial deals increased from `4` to `5`
- Selected documents total increased from `13` to `16`
- Total API calls increased from `228` to `295`

Interpretation:

- more documents were collected
- more partial bundles were assembled
- but none of the additional documents converted a false negative into a true positive under the current benchmark

#### V4 sufficiency

Source: [v4_sufficiency_report.json](/C:/experiments/worktree_d_git/logs/v4_sufficiency_report.json)

- Sufficient for `v4`: `0/9`
- Sufficient for critical fields: `1/9`
- Missing another important document likely exists: `9/9`

Notable differences:

- `rue21-2024` now has `3` reviewed documents instead of `2`
- `steward-health-2024` now has `3` reviewed documents instead of `2`
- `fisker-2024` now surfaces an `other_supporting` document that references the missing first-day declaration

Interpretation:

- the docket-first path improved retrieval breadth
- but still did not break the ingestion-quality ceiling
- the pipeline is finding more supporting material, not enough decisive financing material

### Updated conclusion after this pass

This implementation pass strengthens the evidence that:

- retrieval strategy was part of the problem
- but fixing that alone is still not enough
- the system can now gather more partial context
- the remaining blocker still appears to be deeper source coverage / missing financing docs

So the current best next step remains:

- add a narrow fallback source layer for partial / empty bundles

## Root-Cause Confirmation: Wrong Docket API Path Was Real, But Not Sufficient

A final debugging pass found one real retrieval bug:

- the docket fallback was still using broad V4 search semantics instead of the tighter V3 docket + docket-entry API flow already documented in [WORKTREE_A_RECAP_API.md](/C:/experiments/worktree_d_git/docs/WORKTREE_A_RECAP_API.md)

### Fix implemented

Files changed:

- [agents/retriever.py](/C:/experiments/worktree_d_git/agents/retriever.py)
- [agents/planner.py](/C:/experiments/worktree_d_git/agents/planner.py)
- [test_retriever_docket.py](/C:/experiments/worktree_d_git/test_retriever_docket.py)

Change summary:

- docket fallback now uses:
  - V3 `/dockets/` with `case_name__icontains`, `chapter=11`, court slug, and filing-date filters
  - V3 `/docket-entries/` with `description__icontains` keyword filters
- added a failing test first, then fixed the implementation so that docket fallback now follows the intended V3 path

Verification:

- `python -m unittest test_retriever_docket.py -v`
- full suite still passed afterward

### Result after live rerun

Source: [benchmark_report.json](/C:/experiments/worktree_d_git/logs/benchmark_report.json)

- TP `3`
- FP `0`
- FN `8`
- F1 `0.4286`
- Selected documents total `16`
- Total API calls `246`

Source: [v4_sufficiency_report.json](/C:/experiments/worktree_d_git/logs/v4_sufficiency_report.json)

- Sufficient for `v4`: `0/9`
- Sufficient for critical fields: `1/9`

### Final interpretation after this fix

This was a real bug and it is now fixed.

However, the live rerun still did not improve the plateau. That means:

- the remaining plateau is not primarily caused by the docket API path anymore
- the remaining blocker is the combination of:
  - missing same-case financing documents on CourtListener for the hard cases
  - benchmark truth expecting bundles the current source layer often does not expose
  - deeper source-coverage limitations that CourtListener-only retrieval does not solve

This is the strongest evidence so far that the next real fix is architectural:

- add a fallback source layer beyond CourtListener
