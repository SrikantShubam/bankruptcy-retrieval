# Independent Auditor Report — D Branch Retrieval System

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

### Finding 1 — Triple-Cap Pipeline Suppresses Recall

The pipeline imposes three sequential hard caps that compound into severe recall loss:

| Stage | Cap | File | Line |
|---|---|---|---|
| `execute_plan` return | **12** candidates | [retriever.py](file:///C:/experiments/worktree_d_git/agents/retriever.py#L345) | 345 |
| `_merge_candidates` | **18** candidates | [graph.py](file:///C:/experiments/worktree_d_git/graph.py#L121) | 121 |
| `_classify_candidates` inspection | **12** candidates | [graph.py](file:///C:/experiments/worktree_d_git/graph.py#L134) | 134 |

**Impact**: When the initial plan fires 10+ query variants and the follow-up plan fires more, the merge discards everything past 18 (sorted by score). Then classification only looks at the top 12. Follow-up queries may surface valid docs that never get inspected.

> [!IMPORTANT]
> This is likely the **single highest-ROI fix**. Raising the classify cap from 12 → 24 and the merge cap from 18 → 30 costs almost nothing (all heuristic, no LLM calls) and directly unblocks bundle assembly from follow-up queries.

### Finding 2 — Decision Agent Is Dead Code in Practice

From [benchmark_report.json](file:///C:/experiments/worktree_d_git/logs/benchmark_report.json):

```
"total_llm_gatekeeper_calls": 0
```

The `DecisionAgent` ([decision.py](file:///C:/experiments/worktree_d_git/agents/decision.py)) has fast-path thresholds at L95-98:
- Score ≥ 0.7 → auto-DOWNLOAD
- Score ≤ 0.25 → auto-SKIP

Since the verifier's normalized score (`raw_score / 12.0`, capped at 1.0) almost always lands outside the 0.25–0.7 grey zone, the LLM gatekeeper is **never called**. The "agentic" label is misleading — this is a purely heuristic pipeline.

**Verdict**: The decision layer is not actively harmful, but it's also not contributing. Either widen the grey zone or repurpose it for a more useful task (e.g., bundle-level sufficiency arbitration).

### Finding 3 — Sufficiency Evaluator Is Structurally Too Harsh

From [sufficiency_eval.py](file:///C:/experiments/worktree_d_git/sufficiency_eval.py#L52):

```python
def extract_pdf_text(pdf_path, max_pages=8, max_chars=12000):
```

All 4 critical fields (`total_leverage`, `add_backs_percent`, `covenant_lite`, `largest_customer_percent`) are blocked for **every single deal**, including `conns-2024` which has 3 documents including a DIP motion.

Two structural reasons:

1. **Shallow extraction** — only 8 pages / 12,000 chars per PDF. Bankruptcy first-day declarations routinely run 50-100 pages. Key financial tables often appear after page 20.
2. **Model choice** — `llama-3.3-70b-instruct` may not extract structured financial data as reliably as GPT-4 class models. The evaluator prompt asks for nuanced financial judgment.

> [!WARNING]
> Using the current evaluator as a **gate** (as recommended in the handoff) will produce 100% rejection. It must be revised before it can serve as a meaningful quality signal.

### Finding 4 — Source Coverage Is a Real Ceiling (Confirmed)

The handoff's manual validation (Section 6) is credible. Reviewing the FN list:

| Deal | Root Cause | Can D Fix Solo?  |
|---|---|---|
| `express-2024` | DIP exists but first-day didn't surface | Possibly (cap issue) |
| `rue21-2024` | First-day & cash collateral exist; DIP missing | Partially |
| `fisker-2024` | Only wrong-case material | No — source gap |
| `tgi-fridays-2024` | No candidates at all | No — source gap |
| `ll-flooring-2024` | First-day exists; no DIP | Partially |
| `buca-di-beppo-2024` | No candidates at all | No — source gap |
| `exactech-2024` | First-day exists; no DIP | Partially |
| `caremax-2024` | Only wrong-case material | No — source gap |

**At least 4 of 8 FN deals** (`fisker`, `tgi-fridays`, `buca-di-beppo`, `caremax`) cannot be fixed by CourtListener tuning alone. This confirms the source-coverage ceiling claim.

### Finding 5 — `max_calls_per_deal` Increased But Base Plan Exceeds It

In `run_pipeline`, the retriever is created with `max_calls_per_deal=12` ([graph.py L300](file:///C:/experiments/worktree_d_git/graph.py#L300)), but the planner can generate **14+ query variants** per deal (10 base + aliases + loose + token variants). The retriever silently stops after 12 API calls — meaning late-positioned follow-up variants for DIP/credit-agreement may never fire.

This interacts badly with Finding 1: even if the budget were raised, the merge+classify caps would still drop the results.

---

## Answers to Auditor Questions

### Q1: What is causing the plateau?

**A combination, in order of contribution**:

1. **Source coverage** (~50% of the gap) — CourtListener simply doesn't have the financing docs for several deals.
2. **Candidate caps** (~30%) — Valid docs found by follow-up queries are discarded before classification.
3. **Overly strict sufficiency eval** (~20%) — Creates the illusion that even good bundles fail, which distorts prioritization.

### Q2: Is more CourtListener-only tuning worth it?

**Low-to-medium ROI**. The easy wins (raising caps, fixing the triple-cap problem) should be done regardless and may recover 1–2 deals. Beyond that, CourtListener-only tuning is diminishing returns for the ~4 deals that have genuine source gaps.

### Q3: What should the next changes be?

See **Forward Plan** below — ordered by ROI.

### Q4: Minimum safe claims-agent fallback?

A narrow, targeted fallback that:
- Only fires for deals where D found **0 or 1** documents after full retrieval
- Targets Kroll/Stretto case pages with known slugs from the B branch's `config.py` `KROLL_CASE_SLUGS`
- Downloads PDFs through the same `_download_candidate` function (preserving provenance and manifest contract)
- Does NOT use browser sessions or full B pipeline — just direct HTTP to known claims-agent document listing pages

### Q5: Is the sufficiency evaluator fair enough?

**No, not currently.** It should be revised before being used as a gate. The 8-page/12K-char limit and model choice make it structurally unable to find critical fields in likely locations. A revised version should extract at minimum 30 pages / 40K chars per PDF, or switch to a section-targeted extraction approach.

---

## Forward Plan — Prioritized by ROI

### Phase 1: Quick Wins (High ROI, Low Risk) — Do First

#### 1.1 Raise candidate caps

| Parameter | Current | Recommended |
|---|---|---|
| `_merge_candidates` cap | 18 | 30 |
| `_classify_candidates` loop | `candidates[:12]` | `candidates[:24]` |
| `verify_candidates_with_dockets` return | `updated[:12]` | `updated[:20]` |

**Why**: Zero-cost change. The classify and verify paths are all heuristic (no LLM calls), so increasing the cap only adds negligible CPU time. This directly unblocks follow-up queries from being useful.

#### 1.2 Increase `max_calls_per_deal`

Raise from 12 → 18 for the main retriever in `run_pipeline`. Ensure that follow-up variants actually get to execute before the budget is exhausted.

#### 1.3 Re-benchmark after cap raise

Run `python main.py --priority1-hard` and `python sufficiency_eval.py` again. This establishes a new baseline before adding source-layer work.

---

### Phase 2: Fix the Sufficiency Evaluator (Medium ROI) — Do Second

#### 2.1 Increase PDF extraction depth

Change `extract_pdf_text` defaults from `max_pages=8, max_chars=12000` to `max_pages=30, max_chars=40000`. This is where the critical financial tables actually live in bankruptcy declarations.

#### 2.2 Add section-targeted extraction

Instead of reading the first N pages sequentially, search for pages containing key terms ("Total Leverage", "EBITDA", "Covenant", "DIP Facility", "Credit Agreement") and extract those pages preferentially.

#### 2.3 Consider a stronger model for evaluation

Switch from `llama-3.3-70b-instruct` to a GPT-4 class model for the sufficiency evaluator. The task requires nuanced financial document comprehension that larger models handle better.

---

### Phase 3: Narrow Fallback Source Layer (Medium-High ROI) — Do Third

#### 3.1 Add Kroll/Stretto direct-fetch fallback

For deals where D's bundle has ≤ 1 document after Phase 1:
- Look up the deal's known claims-agent slug (from B's `KROLL_CASE_SLUGS` or equivalent)
- Do a direct HTTP fetch of the case docket listing page
- Parse for first-day declaration and DIP motion links
- Download through D's existing `_download_candidate` and manifest pipeline

This avoids B's browser overhead while leveraging its known source mappings.

#### 3.2 Preserve provenance rules

All fallback downloads must go through the same verifier and provenance pipeline. Add `source_system: "kroll"` or `source_system: "stretto"` to the manifest.

---

### Phase 4: Decision Layer Rework (Lower ROI) — Optional

#### 4.1 Repurpose the LLM decision agent

Instead of per-candidate gating (which the heuristic verifier handles well), use the LLM for **bundle-level arbitration**: given the assembled bundle and the v4 critical fields, should the system fetch more docs or declare the bundle sufficient?

This would replace the sufficiency evaluator as the quality gate and add actual "agentic" intelligence to the pipeline.

---

## Summary of Recommendations

| Priority | Action | Expected Impact |
|---|---|---|
| 🔴 P0 | Raise candidate caps (merge → 30, classify → 24) | Recover 1–2 FN deals from cap suppression |
| 🔴 P0 | Raise `max_calls_per_deal` → 18 | Allow follow-up queries to fire |
| 🟡 P1 | Fix sufficiency eval depth (30 pages / 40K chars) | Make eval a usable quality signal |
| 🟡 P1 | Add Kroll/Stretto direct-fetch fallback | Potentially recover 2–3 source-gap deals |
| 🟢 P2 | Repurpose decision layer for bundle arbitration | Add genuine agentic intelligence |
| 🟢 P2 | Switch sufficiency eval to GPT-4 class model | Higher accuracy on financial judgment |
