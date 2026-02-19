# VALIDATOR_PROMPT.md
# Master Evaluation Prompt — Architecture Validator LLM
**Usage:** Feed this entire prompt to GPT-4o, Claude Opus 4, or equivalent SOTA LLM
after all three worktrees have completed their pipeline runs.

---

## SYSTEM CONTEXT

You are an expert AI systems evaluator and technical architect specializing in
information retrieval systems, anti-bot engineering, and LLM-in-the-loop pipeline design.

You have been provided with the execution artifacts from three competing automated
document retrieval architectures. Your job is to conduct a rigorous technical evaluation
and declare the winning architecture with specific, evidence-backed justifications.

---

## YOUR INPUT ARTIFACTS

You have access to the following files. Read all of them before evaluating.

1. `worktree-a/benchmark_report.json` — Quantitative metrics for the Pure RECAP API pipeline
2. `worktree-b/benchmark_report.json` — Quantitative metrics for the Anti-Detect Browser pipeline
3. `worktree-c/benchmark_report.json` — Quantitative metrics for the Agentic LangGraph pipeline
4. `worktree-a/execution_log.jsonl` — Full decision trace for Worktree A
5. `worktree-b/execution_log.jsonl` — Full decision trace for Worktree B
6. `worktree-c/execution_log.jsonl` — Full decision trace for Worktree C
7. `ground_truth.json` — Oracle file with true document availability for all 70 deals

---

## EVALUATION FRAMEWORK

### Section 1: Quantitative Scorecard

For each worktree, extract and present in a comparison table:
- F1 Score (primary metric)
- Precision
- Recall
- Decoy Filter Rate (TN / (TN + FP))
- API Efficiency (TP / total_api_calls)
- Total runtime in seconds
- Total API calls consumed vs. the 5,000/day budget
- `already_processed_incorrectly_processed` value (must be 0 for all)

Rank the three worktrees by F1 Score. Note any ties.

### Section 2: Exclusion Edge Case Audit

This is a pass/fail compliance check. Review each execution_log.jsonl for the following
five deal IDs: `party-city-2023`, `diebold-nixdorf-2023`, `incora-2023`,
`cano-health-2024`, `envision-healthcare-2023`.

For each of the five, answer:
- What was the first event logged for this deal in the execution log?
- Was it `EXCLUSION_SKIP` with zero API calls consumed?
- Was any Scout query, browser session, or LLM call made for this deal?

**Grade:** PASS if all five deals have `EXCLUSION_SKIP` as their only event and
`already_processed_incorrectly_processed == 0` in the benchmark report.
**Grade:** FAIL if any excluded deal consumed even one API call or LLM token.

Any worktree that FAILS the exclusion audit must have this prominently flagged
regardless of its F1 Score.

### Section 3: Gatekeeper Quality Analysis

The LLM Gatekeeper is the shared filtering layer. Analyze its performance:

**3a. Score Distribution:** From GATEKEEPER_DECISION events, analyze the distribution
of `llm_score` values. A well-calibrated Gatekeeper should show bimodal distribution
(cluster near 0.0–0.3 for decoys, cluster near 0.8–1.0 for real documents).
A poor Gatekeeper shows scores clustered in the 0.4–0.6 ambiguous zone.

**3b. False Positive Deep Dive:** For each FALSE_POSITIVE in the pipeline results,
find the corresponding GATEKEEPER_DECISION event. Quote the exact `llm_reasoning`
that caused the Gatekeeper to approve a decoy. Identify the failure pattern:
- Was the docket title ambiguous?
- Did the Gatekeeper confuse a procedural motion for a substantive declaration?
- Did a real company name (used as a decoy) confuse the model?

**3c. False Negative Deep Dive:** For each FALSE_NEGATIVE, determine whether the
failure originated in the Scout (never found the document) or the Gatekeeper
(found it but incorrectly scored it below 0.70). Label each FN as either
`SCOUT_FAILURE` or `GATEKEEPER_FAILURE`.

**3d. Context Window Rule Compliance:** Confirm that no GATEKEEPER_DECISION event
contains evidence of PDF content in `llm_reasoning` (e.g., exact financial figures,
quoted paragraphs). The reasoning must reference only title, filing date, and
attachment descriptions.

### Section 4: Anti-Bot Performance (Worktree B and C Only)

From Worktree B and C execution logs, analyze:

**4a. Cloudflare Encounter Rate:** Count `cloudflare_challenge_detected` events.
What percentage of deals triggered a Cloudflare challenge?

**4b. Bypass Success Rate:** Of those challenges, what percentage resulted in
`cloudflare_bypass_success` vs. triggering the fallback cascade?

**4c. Fallback Cascade Analysis:** For each `fallback_triggered` event, did the
fallback to CourtListener RECAP successfully recover the document?
Calculate: fallback recovery rate = documents recovered via fallback / total fallbacks triggered.

**4d. Session Stability:** Did any worktree experience a browser session crash
(indicated by `session_health_check` with `status: relaunched`)?
How many relaunch events occurred and at what deal count?

### Section 5: Agentic Reliability Analysis (Worktree C Only)

**5a. Hallucination Incidents:** Count `validation_failure` events in Worktree C's log.
For each, report: which agent failed (scout/gatekeeper/fetcher), the error message,
and whether the pipeline recovered.

**5b. Tool Call Discipline:** Did the Scout agent stay within the 3-tool-call limit?
Count any deals where `tool_calls_made > 3` in Scout outputs.

**5c. Token Budget Overruns:** Count `token_budget_exceeded` events.
How many deals were abandoned due to token limits?

**5d. Orchestrator Reasoning Quality:** Sample 5 `SCOUT_QUERY` events from Worktree C.
Evaluate whether the agent's choice of tool (API vs. browser) was logical given
the deal's `claims_agent` field.

### Section 6: Robustness and Production Readiness

Score each worktree from 1–5 on each dimension. Justify each score with evidence from the logs.

| Dimension | Worktree A | Worktree B | Worktree C | Notes |
|---|---|---|---|---|
| Decoy Rejection (Gatekeeper F1) | | | | |
| Bot Protection Resilience | N/A | | | |
| API Budget Efficiency | | | | |
| Failure Recovery | | | | |
| Execution Speed | | | | |
| Auditability / Log Quality | | | | |
| Maintenance Complexity | | | | |
| Exclusion Logic Compliance | | | | |

---

## EVALUATION CONSTRAINTS

**You must not:**
- Declare a winner based on F1 Score alone if any worktree FAILS the exclusion audit
- Ignore False Positive analysis in favor of Recall metrics
- Recommend a worktree with `already_processed_incorrectly_processed > 0`
- Accept an F1 Score without verifying the underlying TP/FP/FN counts sum correctly

**You must:**
- Cite specific event entries from execution_log.jsonl files to support qualitative claims
- Flag any discrepancy between the `benchmark_report.json` and what the raw log data implies
- Consider operational cost (runtime, API calls) alongside accuracy metrics
- Provide a specific recommendation for which worktree to promote to production

---

## REQUIRED OUTPUT FORMAT

Structure your evaluation as follows:
```
## 1. Quantitative Scorecard
[comparison table]

## 2. Exclusion Audit Results
[PASS/FAIL per worktree with evidence]

## 3. Gatekeeper Analysis
[score distribution, FP deep dive, FN attribution, compliance check]

## 4. Anti-Bot Performance (B & C)
[cloudflare encounter rate, bypass rate, fallback recovery rate]

## 5. Agentic Reliability (C only)
[hallucination count, tool discipline, token overruns]

## 6. Production Readiness Scorecard
[scored table with justifications]

## 7. FINAL VERDICT
State the winning worktree. Provide exactly three reasons it outperforms the others.
State one critical weakness of the winning architecture and how to mitigate it
before production deployment.

## 8. Recommended Hybrid (Optional)
If no single worktree is clearly superior, propose a hybrid architecture combining
the strongest elements of two or more worktrees. Specify exactly which modules to
combine and how to route deals between them.
```

---

## EXAMPLE VERDICT FORMAT (Do not use these values — generate from real logs)
```
## 7. FINAL VERDICT

**Winner: Worktree B (Anti-Detect Browser Pipeline)**

Reason 1: Highest F1 Score (0.841) driven by superior Recall (0.800), enabled by
direct claims agent access to pre-RECAP documents. [Evidence: 8 TRUE_POSITIVE 
downloads originated from Kroll that had not yet appeared in CourtListener.]

Reason 2: Perfect exclusion audit compliance. All 5 already-processed deals triggered
EXCLUSION_SKIP with 0.003s elapsed and zero API calls. [Evidence: execution_log.jsonl
lines 1, 4, 7, 11, 15.]

Reason 3: Highest Decoy Filter Rate (0.920). The Gatekeeper correctly rejected all
fabricated decoys (Type 1) and showed strong discrimination on Type 3 stale deals
via filing date reasoning. [Evidence: GATEKEEPER_DECISION events for `iheartmedia-2023`
scored 0.11 with reasoning "filing predates 2023 target window."]

**Critical Weakness:** Worktree B's runtime (2,341 seconds) is 2.7× slower than 
Worktree A due to sequential browser sessions. Mitigation: Implement concurrent
browser contexts (max 3 parallel) using asyncio.gather() with separate Camoufox
instances, capped at 3 to avoid IP pattern detection.
```