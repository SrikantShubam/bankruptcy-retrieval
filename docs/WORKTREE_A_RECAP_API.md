# WORKTREE_A_RECAP_API.md
# Worktree A — Pure CourtListener RECAP API Pipeline
**Architecture Type:** Server-Side Filtered REST API | No Browser Required
**Worker LLM:** Implement this file as `worktree-a/`

---

## 1. Philosophy

Worktree A is the purest, fastest, most auditable approach. It never launches a browser.
Every document retrieval flows through the CourtListener REST API. The budget is 5,000
requests/day, shared across all 65 active deals (~76 requests/deal maximum).

**Target advantage:** Speed and auditability. Every network call is logged.
**Expected weakness:** Claims agents (Kroll, Epiq) not indexed in RECAP → coverage gaps.

---

## 2. Required Python Libraries
```
httpx>=0.27          # Async HTTP with HTTP/2 support
tenacity>=8.2        # Retry logic with exponential backoff
pydantic>=2.0        # Data validation for API responses
aiolimiter>=1.1      # Async rate limiter (req/second enforcement)
asyncio              # Standard library concurrency
python-dotenv        # Environment variable management
```

**Explicitly NOT required:** Playwright, Selenium, Camoufox, nodriver, or any browser library.

---

## 3. CourtListener API Authentication

- Register free account at https://www.courtlistener.com/sign-in/
- Set `COURTLISTENER_API_TOKEN` in `.env`
- All requests: `Authorization: Token {COURTLISTENER_API_TOKEN}`
- Rate limit enforcer: **max 10 requests/second** (CourtListener's stated limit)
- Daily budget enforcer: **hard stop at 4,800 requests** (200 buffer for retries)

---

## 4. The Scout — API Query Strategy

### Step 1: Case Lookup (1–2 API calls per deal)

Query the `/api/rest/v3/dockets/` endpoint with aggressive server-side filters.

**Endpoint:** `GET https://www.courtlistener.com/api/rest/v3/dockets/`

**Required query parameters:**
```
case_name__icontains={company_name}
date_filed__gte={filing_year}-01-01
date_filed__lte={filing_year}-12-31
court={court_slug}           ← convert "S.D.N.Y." → "nysd", "D. Del." → "deb"
chapter=11
fields=id,case_name,date_filed,court,docket_number
```

**Court slug mapping the worker LLM must implement:**
```
"S.D.N.Y." → "nysd"
"D.N.J."   → "njd"
"D. Del."  → "deb"
"S.D. Tex."→ "txsd"
"M.D. Fla."→ "flmd"
"E.D. Va." → "vaed"
"S.D. Ind."→ "insd"
```

**Budget rule:** If zero results → log NOT_FOUND immediately. Do not paginate. (1 API call spent.)

### Step 2: Targeted Docket Entry Search (2–5 API calls per deal)

Never fetch the full docket. Query `/api/rest/v3/docket-entries/` directly with keyword filters.

**Endpoint:** `GET https://www.courtlistener.com/api/rest/v3/docket-entries/`

**Required query parameters:**
```
docket={docket_id}
description__icontains={keyword}     ← iterate over keyword list below
date_filed__gte={filing_year}-01-01
order_by=date_filed
page_size=5                          ← NEVER exceed 5; we want the first filing
fields=id,description,date_filed,recap_documents
```

**Keyword list (iterate in priority order, stop at first match):**
```python
PRIORITY_KEYWORDS = [
    "first day declaration",
    "declaration in support",
    "DIP motion",
    "debtor in possession financing",
    "cash collateral",
    "capital structure",
    "prepetition debt",
    "credit agreement"
]
```

**Budget enforcement:** Maximum 6 keyword queries per deal. If no match in 6 → NOT_FOUND.

### Step 3: RECAP Document Metadata Extraction (1 API call)

From the docket entry result, extract `recap_documents` array.
Call `/api/rest/v3/recap-documents/{doc_id}/` for the first matching document only.

Extract:
- `description` (attachment description)
- `filepath_local` (RECAP-hosted PDF URL if available)
- `is_available` (boolean)

Pass `description` and parent docket entry `description` to the Gatekeeper.
**DO NOT download the PDF at this step.**

---

## 5. The Evaluator — Gatekeeper Integration

Pass this payload to `gatekeeper.py`:
```python
candidate = CandidateDocument(
    deal_id=deal.deal_id,
    source="courtlistener",
    docket_entry_id=str(entry_id),
    docket_title=entry_description,           # From docket entry
    filing_date=entry_date_filed,
    attachment_descriptions=[doc_description], # From recap-document
    resolved_pdf_url=filepath_local_url,
    api_calls_consumed=calls_so_far
)
```

If `gatekeeper.evaluate(candidate).verdict == "DOWNLOAD"` → proceed to Fetcher.
If `"SKIP"` → log and move to next deal.

---

## 6. The Fetcher — RECAP PDF Download

RECAP-hosted PDFs are served directly from CourtListener's S3 bucket.
No bot protection. Use simple `httpx` streaming download.
```
PDF URL format: https://storage.courtlistener.com/recap/{filepath_local}
```

**Fetcher logic:**
1. If `is_available == true` → stream download directly (no auth required for RECAP PDFs)
2. If `is_available == false` → log `FETCH_FAILED: not_in_recap` → do NOT attempt PACER
3. Save to `./downloads/{deal_id}/{filename}.pdf`
4. Log `pipeline_status: "DOWNLOADED"`

**Streaming implementation requirement:**
Use `httpx.AsyncClient` with `stream=True`. Write chunks to disk.
Timeout: 30 seconds. Max file size: 50MB (skip if larger — likely a full docket).

---

## 7. Rate Limiter Implementation

Worker LLM must implement a module-level rate limiter:
```
- Global request counter persisted to `rate_limit_state.json`
- On each API call: increment counter, check against 4,800 daily limit
- If counter >= 4,800: raise DailyBudgetExhausted exception, halt pipeline
- Reset counter at midnight UTC (check timestamp in state file)
- Per-second limiter: max 10 requests/second using aiolimiter.AsyncLimiter
```

---

## 8. Retry Policy
```
- HTTP 429 (rate limited): exponential backoff starting at 2s, max 5 retries
- HTTP 5xx: retry 3 times with 5s delay
- HTTP 404: do not retry, log NOT_FOUND
- Network timeout: retry 2 times, then log FETCH_FAILED
```

Use `tenacity.retry` decorator with `wait_exponential` and `stop_after_attempt`.

---

## 9. Logging Events Specific to Worktree A

Append to `execution_log.jsonl` at each decision point:
```json
{"event": "api_call", "endpoint": "/api/rest/v3/dockets/", "params": {...}, "status_code": 200, "results_count": 1, "deal_id": "wework-2023", "api_calls_total": 3}
{"event": "gatekeeper_decision", "verdict": "DOWNLOAD", "score": 0.91, "reasoning": "...", "deal_id": "wework-2023"}
{"event": "fetch_complete", "file_path": "./downloads/wework-2023/first_day_decl.pdf", "size_bytes": 2048000, "deal_id": "wework-2023"}
{"event": "budget_warning", "api_calls_used": 4500, "remaining": 300, "timestamp_utc": "..."}
```