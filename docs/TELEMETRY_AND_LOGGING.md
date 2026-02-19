# TELEMETRY_AND_LOGGING.md
# Benchmarking, Telemetry Schema, and F1 Score Computation
**Worker LLM:** Implement this as `shared/telemetry.py` and `shared/benchmark.py`

---

## 1. The execution_log.jsonl Schema

Every line is a self-contained JSON object. The file is append-only.
**Never rewrite or truncate this file mid-run.**

### Universal fields (all event types):
```json
{
  "event_type": "string — see event taxonomy below",
  "worktree": "A | B | C",
  "deal_id": "string",
  "company_name": "string",
  "timestamp_utc": "ISO 8601 — e.g. 2024-11-15T14:23:01.442Z",
  "elapsed_seconds": "float — seconds since pipeline start for this deal"
}
```

### Event Taxonomy

**`EXCLUSION_SKIP`** — Emitted immediately when a deal is in the excluded set:
```json
{
  "event_type": "EXCLUSION_SKIP",
  "worktree": "A",
  "deal_id": "party-city-2023",
  "company_name": "Party City",
  "timestamp_utc": "...",
  "elapsed_seconds": 0.003,
  "reason": "already_processed"
}
```

**`SCOUT_QUERY`** — Emitted for each search attempt:
```json
{
  "event_type": "SCOUT_QUERY",
  "worktree": "A",
  "deal_id": "wework-2023",
  "company_name": "WeWork",
  "timestamp_utc": "...",
  "elapsed_seconds": 1.22,
  "source": "courtlistener | kroll | stretto | epiq",
  "query_params": {"case_name__icontains": "WeWork", "date_filed__gte": "2023-01-01"},
  "results_count": 3,
  "api_calls_consumed_this_query": 1,
  "api_calls_total": 2
}
```

**`GATEKEEPER_DECISION`** — Emitted after every LLM evaluation:
```json
{
  "event_type": "GATEKEEPER_DECISION",
  "worktree": "A",
  "deal_id": "wework-2023",
  "company_name": "WeWork",
  "timestamp_utc": "...",
  "elapsed_seconds": 3.87,
  "docket_title": "Declaration of David Tolley in Support of First Day Motions",
  "attachment_descriptions": ["Exhibit A - Capital Structure Overview"],
  "llm_model": "meta/llama-3.1-8b-instruct",
  "llm_verdict": "DOWNLOAD",
  "llm_score": 0.94,
  "llm_reasoning": "Title explicitly references First Day Motions and capital structure.",
  "llm_tokens_used": 112
}
```

**`FETCH_RESULT`** — Emitted after download attempt:
```json
{
  "event_type": "FETCH_RESULT",
  "worktree": "A",
  "deal_id": "wework-2023",
  "company_name": "WeWork",
  "timestamp_utc": "...",
  "elapsed_seconds": 8.44,
  "success": true,
  "local_file_path": "./downloads/wework-2023/first_day_decl.pdf",
  "file_size_bytes": 2847392,
  "fetch_method": "httpx_stream | browser_download | browser_page",
  "bot_bypass_used": false,
  "failure_reason": null
}
```

**`PIPELINE_TERMINAL`** — Final status for each deal. ONE per deal, always:
```json
{
  "event_type": "PIPELINE_TERMINAL",
  "worktree": "A",
  "deal_id": "wework-2023",
  "company_name": "WeWork",
  "timestamp_utc": "...",
  "elapsed_seconds": 8.51,
  "pipeline_status": "DOWNLOADED | SKIPPED | NOT_FOUND | FETCH_FAILED | ALREADY_PROCESSED",
  "total_api_calls_this_deal": 5,
  "total_llm_calls_this_deal": 1,
  "downloaded_file": "./downloads/wework-2023/first_day_decl.pdf"
}
```

---

## 2. ground_truth.json Schema (Reference)
```json
{
  "{deal_id}": {
    "has_financial_data": "boolean — true if a qualifying document genuinely exists",
    "already_processed": "boolean — true for the 5 excluded deals",
    "expected_doc_type": "string or null — 'First Day Declaration' | 'DIP Motion' | null"
  }
}
```

---

## 3. Classification Logic

After the pipeline completes, the benchmarking script classifies each deal
by comparing `PIPELINE_TERMINAL.pipeline_status` against `ground_truth.json`:
```
FOR each deal in pipeline results:

  IF ground_truth[deal_id].already_processed == true:
    → classification = "ALREADY_PROCESSED" (excluded from F1 calculation)

  ELIF pipeline_status == "DOWNLOADED" AND ground_truth.has_financial_data == true:
    → classification = TRUE_POSITIVE (TP)

  ELIF pipeline_status == "DOWNLOADED" AND ground_truth.has_financial_data == false:
    → classification = FALSE_POSITIVE (FP)  ← downloaded a decoy

  ELIF pipeline_status IN ["SKIPPED","NOT_FOUND"] AND ground_truth.has_financial_data == false:
    → classification = TRUE_NEGATIVE (TN)  ← correctly skipped a decoy

  ELIF pipeline_status IN ["SKIPPED","NOT_FOUND"] AND ground_truth.has_financial_data == true:
    → classification = FALSE_NEGATIVE (FN)  ← missed a real document

  ELIF pipeline_status == "FETCH_FAILED":
    → classification = FALSE_NEGATIVE (FN)  ← found it but couldn't get it
```

---

## 4. F1 Score Formula

The benchmark script must compute these metrics exactly:
```
Precision = TP / (TP + FP)
  ↳ "Of everything we downloaded, how much was genuinely useful?"

Recall = TP / (TP + FN)
  ↳ "Of all real documents that existed, how many did we find?"

F1 Score = 2 × (Precision × Recall) / (Precision + Recall)
  ↳ Harmonic mean. Primary benchmark metric.

Coverage = (TP + FP) / total_active_deals
  ↳ total_active_deals = 65 (70 minus 5 already_processed)

Decoy Filter Rate = TN / (TN + FP)
  ↳ How good is the Gatekeeper at rejecting decoys?

API Efficiency = TP / total_api_calls_all_deals
  ↳ True positives per API call consumed
```

**Edge case handling:**
- If TP + FP == 0: Precision = 0.0 (no downloads made)
- If TP + FN == 0: Recall = 1.0 (no real documents existed — pathological case)
- If Precision + Recall == 0: F1 = 0.0

---

## 5. Benchmark Report Output

The script writes `benchmark_report.json`:
```json
{
  "worktree": "A",
  "run_timestamp_utc": "...",
  "deals_total": 70,
  "deals_already_processed": 5,
  "deals_active": 65,
  "true_positives": 28,
  "false_positives": 3,
  "true_negatives": 21,
  "false_negatives": 13,
  "precision": 0.903,
  "recall": 0.683,
  "f1_score": 0.778,
  "coverage": 0.477,
  "decoy_filter_rate": 0.875,
  "api_efficiency": 0.043,
  "total_api_calls": 651,
  "total_llm_gatekeeper_calls": 42,
  "total_runtime_seconds": 847.3,
  "already_processed_correctly_excluded": 5,
  "already_processed_incorrectly_processed": 0
}
```

The field `already_processed_incorrectly_processed` must be 0.
If it is > 0, the exclusion logic has a critical bug.

---

## 6. The Comparative Dashboard

The final benchmarking script `compare_worktrees.py` ingests all three
`benchmark_report.json` files and prints:
```
╔══════════════════════════════════════════════════════════╗
║         ARCHITECTURE BENCHMARK COMPARISON                ║
╠══════════════╦═══════════╦═══════════╦═══════════════════╣
║ Metric       ║ Worktree A║ Worktree B║ Worktree C        ║
╠══════════════╬═══════════╬═══════════╬═══════════════════╣
║ F1 Score     ║ 0.778     ║ 0.841     ║ 0.792             ║
║ Precision    ║ 0.903     ║ 0.886     ║ 0.850             ║
║ Recall       ║ 0.683     ║ 0.800     ║ 0.746             ║
║ API Calls    ║ 651       ║ 234       ║ 312               ║
║ Runtime (s)  ║ 847       ║ 2341      ║ 3102              ║
║ Decoy Filter ║ 0.875     ║ 0.920     ║ 0.880             ║
╚══════════════╩═══════════╩═══════════╩═══════════════════╝
WINNER by F1: Worktree B (0.841)
```

Note: values above are illustrative. Actual values come from pipeline runs.