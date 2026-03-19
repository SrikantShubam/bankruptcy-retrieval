# Consolidated Auditor File

Generated on 2026-03-19 after a repository search for auditor markdown files.

Files found:
- C:\experiments\worktree_d_git\docs\AUDITOR_HANDOFF_2026-03-19.md
- C:\experiments\worktree_d_git\docs\auditor_report.md
- C:\experiments\worktree-b\auditor.md

This file concatenates the two D-specific auditor documents so an external auditor can review the full context in one place.

---

## Source 1: AUDITOR_HANDOFF_2026-03-19.md

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

`v4` is fundamentally multi-document oriented. It expects a useful deal corpus, not a single â€œbest PDFâ€.

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
- the â€œagenticâ€ label is not currently producing meaningful selector intelligence in the final path

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

That reviewerâ€™s highest-ROI next move was:

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
   - does not reintroduce Bâ€™s brittleness
   - preserves Dâ€™s provenance and manifest structure

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


---

## Source 2: auditor_report.md

# Independent Auditor Report â€” D Branch Retrieval System

**Date**: 2026-03-19  
**Scope**: Independent code-level review of `worktree_d_git` pipeline, reports, and handoff document  
**Auditor Input**: [AUDITOR_HANDOFF_2026-03-19.md](file:///C:/experiments/worktree_d_git/docs/AUDITOR_HANDOFF_2026-03-19.md)

---

## Executive Summary

The D branch is architecturally sound, with clean provenance, good infra resilience, and bundle-oriented output. However, it is **plateaued at F1 0.43 / 0% v4-sufficiency** due to a combination of:

1. **Hard candidate caps** that silently discard recall
2. **CourtListener source-coverage ceiling** for financing docs
3. A **dormant LLM decision layer** that never fires
4. An **overly strict sufficiency evaluator** that conflates "shallow text extraction" with "missing documents"

The handoff's own diagnosis is largely correct. This report independently confirms the key claims and adds concrete, prioritized next steps.

---

## Independent Findings

### Finding 1 â€” Triple-Cap Pipeline Suppresses Recall

The pipeline imposes three sequential hard caps that compound into severe recall loss:

| Stage | Cap | File | Line |
|---|---|---|---|
| `execute_plan` return | **12** candidates | [retriever.py](file:///C:/experiments/worktree_d_git/agents/retriever.py#L345) | 345 |
| `_merge_candidates` | **18** candidates | [graph.py](file:///C:/experiments/worktree_d_git/graph.py#L121) | 121 |
| `_classify_candidates` inspection | **12** candidates | [graph.py](file:///C:/experiments/worktree_d_git/graph.py#L134) | 134 |

**Impact**: When the initial plan fires 10+ query variants and the follow-up plan fires more, the merge discards everything past 18 (sorted by score). Then classification only looks at the top 12. Follow-up queries may surface valid docs that never get inspected.

> [!IMPORTANT]
> This is likely the **single highest-ROI fix**. Raising the classify cap from 12 â†’ 24 and the merge cap from 18 â†’ 30 costs almost nothing (all heuristic, no LLM calls) and directly unblocks bundle assembly from follow-up queries.

### Finding 2 â€” Decision Agent Is Dead Code in Practice

From [benchmark_report.json](file:///C:/experiments/worktree_d_git/logs/benchmark_report.json):

```
"total_llm_gatekeeper_calls": 0
```

The `DecisionAgent` ([decision.py](file:///C:/experiments/worktree_d_git/agents/decision.py)) has fast-path thresholds at L95-98:
- Score â‰¥ 0.7 â†’ auto-DOWNLOAD
- Score â‰¤ 0.25 â†’ auto-SKIP

Since the verifier's normalized score (`raw_score / 12.0`, capped at 1.0) almost always lands outside the 0.25â€“0.7 grey zone, the LLM gatekeeper is **never called**. The "agentic" label is misleading â€” this is a purely heuristic pipeline.

**Verdict**: The decision layer is not actively harmful, but it's also not contributing. Either widen the grey zone or repurpose it for a more useful task (e.g., bundle-level sufficiency arbitration).

### Finding 3 â€” Sufficiency Evaluator Is Structurally Too Harsh

From [sufficiency_eval.py](file:///C:/experiments/worktree_d_git/sufficiency_eval.py#L52):

```python
def extract_pdf_text(pdf_path, max_pages=8, max_chars=12000):
```

All 4 critical fields (`total_leverage`, `add_backs_percent`, `covenant_lite`, `largest_customer_percent`) are blocked for **every single deal**, including `conns-2024` which has 3 documents including a DIP motion.

Two structural reasons:

1. **Shallow extraction** â€” only 8 pages / 12,000 chars per PDF. Bankruptcy first-day declarations routinely run 50-100 pages. Key financial tables often appear after page 20.
2. **Model choice** â€” `llama-3.3-70b-instruct` may not extract structured financial data as reliably as GPT-4 class models. The evaluator prompt asks for nuanced financial judgment.

> [!WARNING]
> Using the current evaluator as a **gate** (as recommended in the handoff) will produce 100% rejection. It must be revised before it can serve as a meaningful quality signal.

### Finding 4 â€” Source Coverage Is a Real Ceiling (Confirmed)

The handoff's manual validation (Section 6) is credible. Reviewing the FN list:

| Deal | Root Cause | Can D Fix Solo?  |
|---|---|---|
| `express-2024` | DIP exists but first-day didn't surface | Possibly (cap issue) |
| `rue21-2024` | First-day & cash collateral exist; DIP missing | Partially |
| `fisker-2024` | Only wrong-case material | No â€” source gap |
| `tgi-fridays-2024` | No candidates at all | No â€” source gap |
| `ll-flooring-2024` | First-day exists; no DIP | Partially |
| `buca-di-beppo-2024` | No candidates at all | No â€” source gap |
| `exactech-2024` | First-day exists; no DIP | Partially |
| `caremax-2024` | Only wrong-case material | No â€” source gap |

**At least 4 of 8 FN deals** (`fisker`, `tgi-fridays`, `buca-di-beppo`, `caremax`) cannot be fixed by CourtListener tuning alone. This confirms the source-coverage ceiling claim.

### Finding 5 â€” `max_calls_per_deal` Increased But Base Plan Exceeds It

In `run_pipeline`, the retriever is created with `max_calls_per_deal=12` ([graph.py L300](file:///C:/experiments/worktree_d_git/graph.py#L300)), but the planner can generate **14+ query variants** per deal (10 base + aliases + loose + token variants). The retriever silently stops after 12 API calls â€” meaning late-positioned follow-up variants for DIP/credit-agreement may never fire.

This interacts badly with Finding 1: even if the budget were raised, the merge+classify caps would still drop the results.

---

## Answers to Auditor Questions

### Q1: What is causing the plateau?

**A combination, in order of contribution**:

1. **Source coverage** (~50% of the gap) â€” CourtListener simply doesn't have the financing docs for several deals.
2. **Candidate caps** (~30%) â€” Valid docs found by follow-up queries are discarded before classification.
3. **Overly strict sufficiency eval** (~20%) â€” Creates the illusion that even good bundles fail, which distorts prioritization.

### Q2: Is more CourtListener-only tuning worth it?

**Low-to-medium ROI**. The easy wins (raising caps, fixing the triple-cap problem) should be done regardless and may recover 1â€“2 deals. Beyond that, CourtListener-only tuning is diminishing returns for the ~4 deals that have genuine source gaps.

### Q3: What should the next changes be?

See **Forward Plan** below â€” ordered by ROI.

### Q4: Minimum safe claims-agent fallback?

A narrow, targeted fallback that:
- Only fires for deals where D found **0 or 1** documents after full retrieval
- Targets Kroll/Stretto case pages with known slugs from the B branch's `config.py` `KROLL_CASE_SLUGS`
- Downloads PDFs through the same `_download_candidate` function (preserving provenance and manifest contract)
- Does NOT use browser sessions or full B pipeline â€” just direct HTTP to known claims-agent document listing pages

### Q5: Is the sufficiency evaluator fair enough?

**No, not currently.** It should be revised before being used as a gate. The 8-page/12K-char limit and model choice make it structurally unable to find critical fields in likely locations. A revised version should extract at minimum 30 pages / 40K chars per PDF, or switch to a section-targeted extraction approach.

---

## Forward Plan â€” Prioritized by ROI

### Phase 1: Quick Wins (High ROI, Low Risk) â€” Do First

#### 1.1 Raise candidate caps

| Parameter | Current | Recommended |
|---|---|---|
| `_merge_candidates` cap | 18 | 30 |
| `_classify_candidates` loop | `candidates[:12]` | `candidates[:24]` |
| `verify_candidates_with_dockets` return | `updated[:12]` | `updated[:20]` |

**Why**: Zero-cost change. The classify and verify paths are all heuristic (no LLM calls), so increasing the cap only adds negligible CPU time. This directly unblocks follow-up queries from being useful.

#### 1.2 Increase `max_calls_per_deal`

Raise from 12 â†’ 18 for the main retriever in `run_pipeline`. Ensure that follow-up variants actually get to execute before the budget is exhausted.

#### 1.3 Re-benchmark after cap raise

Run `python main.py --priority1-hard` and `python sufficiency_eval.py` again. This establishes a new baseline before adding source-layer work.

---

### Phase 2: Fix the Sufficiency Evaluator (Medium ROI) â€” Do Second

#### 2.1 Increase PDF extraction depth

Change `extract_pdf_text` defaults from `max_pages=8, max_chars=12000` to `max_pages=30, max_chars=40000`. This is where the critical financial tables actually live in bankruptcy declarations.

#### 2.2 Add section-targeted extraction

Instead of reading the first N pages sequentially, search for pages containing key terms ("Total Leverage", "EBITDA", "Covenant", "DIP Facility", "Credit Agreement") and extract those pages preferentially.

#### 2.3 Consider a stronger model for evaluation

Switch from `llama-3.3-70b-instruct` to a GPT-4 class model for the sufficiency evaluator. The task requires nuanced financial document comprehension that larger models handle better.

---

### Phase 3: Narrow Fallback Source Layer (Medium-High ROI) â€” Do Third

#### 3.1 Add Kroll/Stretto direct-fetch fallback

For deals where D's bundle has â‰¤ 1 document after Phase 1:
- Look up the deal's known claims-agent slug (from B's `KROLL_CASE_SLUGS` or equivalent)
- Do a direct HTTP fetch of the case docket listing page
- Parse for first-day declaration and DIP motion links
- Download through D's existing `_download_candidate` and manifest pipeline

This avoids B's browser overhead while leveraging its known source mappings.

#### 3.2 Preserve provenance rules

All fallback downloads must go through the same verifier and provenance pipeline. Add `source_system: "kroll"` or `source_system: "stretto"` to the manifest.

---

### Phase 4: Decision Layer Rework (Lower ROI) â€” Optional

#### 4.1 Repurpose the LLM decision agent

Instead of per-candidate gating (which the heuristic verifier handles well), use the LLM for **bundle-level arbitration**: given the assembled bundle and the v4 critical fields, should the system fetch more docs or declare the bundle sufficient?

This would replace the sufficiency evaluator as the quality gate and add actual "agentic" intelligence to the pipeline.

---

## Summary of Recommendations

| Priority | Action | Expected Impact |
|---|---|---|
| ðŸ”´ P0 | Raise candidate caps (merge â†’ 30, classify â†’ 24) | Recover 1â€“2 FN deals from cap suppression |
| ðŸ”´ P0 | Raise `max_calls_per_deal` â†’ 18 | Allow follow-up queries to fire |
| ðŸŸ¡ P1 | Fix sufficiency eval depth (30 pages / 40K chars) | Make eval a usable quality signal |
| ðŸŸ¡ P1 | Add Kroll/Stretto direct-fetch fallback | Potentially recover 2â€“3 source-gap deals |
| ðŸŸ¢ P2 | Repurpose decision layer for bundle arbitration | Add genuine agentic intelligence |
| ðŸŸ¢ P2 | Switch sufficiency eval to GPT-4 class model | Higher accuracy on financial judgment |

---

## Source 3: Post-Report Implementation Log

After reading `docs/auditor_report.md`, the following changes were implemented in D:

- raised merge cap to `30` and classification cap to `24` in [graph.py](/C:/experiments/worktree_d_git/graph.py)
- raised retriever return / verify cap to `20` in [agents/retriever.py](/C:/experiments/worktree_d_git/agents/retriever.py)
- raised `max_calls_per_deal` from `12` to `18` in [graph.py](/C:/experiments/worktree_d_git/graph.py)
- deepened the `v4` sufficiency evaluator from `8` pages / `12,000` chars to `30` pages / `40,000` chars in [sufficiency_eval.py](/C:/experiments/worktree_d_git/sufficiency_eval.py)
- added targeted page prioritization for leverage / EBITDA / covenant / DIP / credit-agreement terms
- added regression coverage in [test_sufficiency_eval.py](/C:/experiments/worktree_d_git/test_sufficiency_eval.py)

Verification passed:

- `python -m unittest test_smoke_scoring.py test_planner_hard_cases.py test_retriever_retries.py test_main_args.py test_d_provenance.py test_sufficiency_eval.py -v`

Post-change benchmark result from [benchmark_report.json](/C:/experiments/worktree_d_git/logs/benchmark_report.json):

- TP `3`
- FP `0`
- FN `8`
- F1 `0.4286`
- required doc-type recall `0.4545`
- total API calls `228`

Post-change sufficiency result from [v4_sufficiency_report.json](/C:/experiments/worktree_d_git/logs/v4_sufficiency_report.json):

- sufficient for `v4`: `0/9`
- sufficient for critical fields: `1/9`
- missing important document likely exists: `9/9`

Net effect:

- the quick wins did not move the strict retrieval benchmark
- they did make the sufficiency evaluator more informative
- `hornblower-2024` is now judged sufficient for critical fields, where previously no deal was
- the main bottleneck still appears to be source coverage rather than just cap pressure or evaluator shallowness

---

## Source 4: Docket-First / Alias Expansion Implementation Log

A further implementation pass targeted the hypothesis that the `0.4286` plateau was still partly a retrieval-strategy issue rather than only a source ceiling.

Changes implemented:

- planner now generates alias-expanded and yearless docket queries in [agents/planner.py](/C:/experiments/worktree_d_git/agents/planner.py)
- retriever now honors per-variant `available_only`, accepts docket variants explicitly, and expands docket fallback breadth in [agents/retriever.py](/C:/experiments/worktree_d_git/agents/retriever.py)
- graph now triggers docket fallback when there are `<= 1` same-case confirmed candidates, not only when retrieval fully collapses, in [graph.py](/C:/experiments/worktree_d_git/graph.py)
- new tests were added in:
  - [test_planner_hard_cases.py](/C:/experiments/worktree_d_git/test_planner_hard_cases.py)
  - [test_d_provenance.py](/C:/experiments/worktree_d_git/test_d_provenance.py)

Verification passed:

- `python -m unittest test_smoke_scoring.py test_planner_hard_cases.py test_retriever_retries.py test_main_args.py test_d_provenance.py test_sufficiency_eval.py -v`

Post-change benchmark result from [benchmark_report.json](/C:/experiments/worktree_d_git/logs/benchmark_report.json):

- TP `3`
- FP `0`
- FN `8`
- F1 `0.4286`
- bundle partial deals `5`
- selected documents total `16`
- total API calls `295`

Post-change sufficiency result from [v4_sufficiency_report.json](/C:/experiments/worktree_d_git/logs/v4_sufficiency_report.json):

- sufficient for `v4`: `0/9`
- sufficient for critical fields: `1/9`
- missing important document likely exists: `9/9`

Net effect:

- the docket-first / alias path increased retrieval breadth
- it did not improve TP/FN on the hard benchmark
- it surfaced more partial bundles and supporting documents, especially for `rue21-2024`, `steward-health-2024`, and `fisker-2024`
- the plateau now looks even more like a deeper source-coverage problem, not just a query-construction problem

---

## Source 5: V3 Docket Root-Cause Fix

A final debugging pass found one real implementation bug:

- the docket fallback was still using the broad V4 search path instead of the tighter V3 `/dockets/` and `/docket-entries/` flow already documented in the repo

Fix implemented in:

- [agents/retriever.py](/C:/experiments/worktree_d_git/agents/retriever.py)
- [agents/planner.py](/C:/experiments/worktree_d_git/agents/planner.py)
- [test_retriever_docket.py](/C:/experiments/worktree_d_git/test_retriever_docket.py)

What changed:

- V3 docket search now uses:
  - `case_name__icontains`
  - `chapter=11`
  - court slug filter
  - filing-date window
- V3 docket-entry lookup now uses server-side `description__icontains` keyword filtering
- a dedicated failing test was added first and then made green

Verification passed:

- `python -m unittest test_retriever_docket.py -v`
- full D suite remained green

Post-change live result:

- benchmark still `F1 0.4286`, TP `3`, FN `8`
- sufficiency still `0/9` for `v4`, `1/9` for critical fields

Net effect:

- the wrong docket API path was a real bug
- it is now fixed
- fixing it still did not move the plateau
- this is the strongest evidence in the repo that the remaining blocker is architectural and source-layer-related, not just another local retrieval bug
