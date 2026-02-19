# ARCHITECTURE_MASTER.md
# Document Retrieval System — Global Architecture Specification
**Version:** 1.0 | **Status:** Handoff to Worker LLMs

---

## 1. Mission Statement

This system autonomously retrieves Chapter 11 bankruptcy documents (First Day Declarations,
DIP Motions, Capital Structure summaries) from zero-cost public sources, filters out
procedural noise using an LLM Gatekeeper, and benchmarks three competing retrieval
architectures against each other using precision/recall telemetry.

---

## 2. The Three Worktrees (Parallel Architectures)

| Worktree | Name | Primary Mechanism |
|---|---|---|
| A | Pure RECAP API Pipeline | CourtListener REST API only, no browser |
| B | Hardened Headless Pipeline | Anti-detect browser targeting claims agents |
| C | Autonomous Agentic Pipeline | LangGraph multi-agent with tool-use |

Each worktree is an isolated git branch. They share:
- The same `deals_dataset.json` input (70 deals)
- The same `ground_truth.json` validation file
- The same `execution_log.jsonl` schema
- The same LLM Gatekeeper interface contract

---

## 3. The Universal Agent Flow
```
[Dataset Loader]
      │
      ▼
[Exclusion Filter] ── "already_processed": true ──► [Log: ALREADY_PROCESSED] ──► STOP
      │
      ▼ (65 active deals)
[SCOUT AGENT]
  - Searches CourtListener RECAP API and/or claims agent sites
  - Emits: list of CandidateDocuments (metadata only, no PDF bytes)
      │
      ▼
[EVALUATOR / LLM GATEKEEPER]
  - Receives: docket title + attachment descriptions + filing date
  - FORBIDDEN: downloading the PDF
  - Emits: verdict {DOWNLOAD | SKIP} + score (0.0–1.0) + reasoning string
      │
      ├── SKIP ──► [Log: TRUE_NEGATIVE or FALSE_NEGATIVE at eval time]
      │
      ▼ DOWNLOAD
[FETCHER AGENT]
  - Downloads the PDF from the resolved URL
  - Bypasses bot protections if required (Worktree B/C only)
  - Emits: local file path or failure reason
      │
      ▼
[TELEMETRY ENGINE]
  - Cross-references outcome against ground_truth.json
  - Classifies: TP / FP / FN / TN / ALREADY_PROCESSED
  - Appends to execution_log.jsonl
```

---

## 4. The 70-Deal Dataset Contract

The pipeline ingests `deals_dataset.json`. Each entry conforms to:
```json
{
  "deal_id": "string — unique slug e.g. 'wework-2023'",
  "company_name": "string",
  "filing_year": "integer",
  "court": "string — e.g. 'S.D.N.Y.'",
  "chapter": 11,
  "already_processed": "boolean",
  "pacer_case_id": "string or null — CourtListener case ID if known",
  "claims_agent": "string or null — e.g. 'Kroll', 'Stretto', 'Epiq'",
  "target_doc_types": ["First Day Declaration", "DIP Motion"]
}
```

---

## 5. The 5-Deal Exclusion Logic

This is the FIRST operation executed before any API call or browser launch.

**Implementation rule for all worker LLMs:**
```
EXCLUDED_SET = {
    "Party City", "Diebold Nixdorf", "Incora",
    "Cano Health", "Envision Healthcare"
}

On dataset load:
  FOR each deal in deals_dataset.json:
    IF deal.company_name IN EXCLUDED_SET OR deal.already_processed == true:
      emit log event: {status: "ALREADY_PROCESSED", api_calls_used: 0}
      CONTINUE to next deal  ← zero API calls, zero browser sessions
```

The exclusion check must occur BEFORE the Scout initializes any HTTP session.
This is non-negotiable to preserve the 5,000 req/day CourtListener budget.

---

## 6. The CandidateDocument Data Contract

The Scout emits this object to the Evaluator. No PDF bytes. No full text.
```json
{
  "deal_id": "wework-2023",
  "source": "courtlistener | kroll | stretto | epiq",
  "docket_entry_id": "string",
  "docket_title": "string — raw title from docket",
  "filing_date": "YYYY-MM-DD",
  "attachment_descriptions": ["string", "string"],
  "resolved_pdf_url": "string or null",
  "api_calls_consumed": "integer"
}
```

---

## 7. The LLM Gatekeeper Interface Contract

All three worktrees must call the Gatekeeper identically:

**Input:** CandidateDocument (metadata fields only)  
**Model options:** `meta/llama-3.1-8b-instruct` via NVIDIA NIM (free tier)  
or `meta-llama/llama-3.1-8b-instruct:free` via OpenRouter  
**Max tokens:** 150  
**Temperature:** 0.0 (deterministic)

**Required output schema:**
```json
{
  "verdict": "DOWNLOAD | SKIP",
  "score": 0.85,
  "reasoning": "One sentence max. No PDF content referenced.",
  "token_count": 87
}
```

**Scoring threshold:** score ≥ 0.70 → DOWNLOAD

---

## 8. The EvaluationResult Data Contract

After Fetcher completes (or is bypassed), emit this to the Telemetry Engine:
```json
{
  "deal_id": "string",
  "company_name": "string",
  "pipeline_status": "ALREADY_PROCESSED | DOWNLOADED | SKIPPED | FETCH_FAILED | NOT_FOUND",
  "llm_verdict": "DOWNLOAD | SKIP | null",
  "llm_score": "float or null",
  "llm_reasoning": "string or null",
  "local_file_path": "string or null",
  "total_api_calls": "integer",
  "worktree": "A | B | C",
  "timestamp_utc": "ISO 8601"
}
```

---

## 9. Forbidden Patterns (All Worker LLMs Must Avoid)

- DO NOT download a PDF to decide whether to download it
- DO NOT paginate entire dockets when server-side filters suffice
- DO NOT launch a browser session for a deal in the EXCLUDED_SET
- DO NOT hardcode CourtListener case IDs — resolve them dynamically via search
- DO NOT make more than 3 Gatekeeper LLM calls per deal (token budget)
- DO NOT store raw PDF bytes in execution_log.jsonl

---

## 10. Directory Structure (All Worktrees)
```
worktree-{a|b|c}/
├── main.py                  # Entrypoint
├── scout.py                 # Source-specific search logic
├── gatekeeper.py            # LLM evaluator (shared interface)
├── fetcher.py               # Download + bot-bypass logic
├── telemetry.py             # Logging + F1 computation
├── config.py                # Constants, excluded set, thresholds
├── deals_dataset.json       # Symlink to shared dataset
├── ground_truth.json        # Symlink to shared ground truth
└── execution_log.jsonl      # Runtime output (append-only)
```