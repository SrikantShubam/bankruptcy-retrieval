# WORKTREE_C_MULTI_AGENT.md
# Worktree C — Autonomous Agentic Pipeline (LangGraph + Browser-Use)
**Architecture Type:** Multi-Agent Orchestration with Tool-Use
**Worker LLM:** Implement this file as `worktree-c/`

---

## 1. Philosophy

Worktree C replaces hard-coded navigation logic with an autonomous agent that
decides how to find each document. The orchestrator uses LangGraph to manage
state across a graph of specialized sub-agents. Browser-Use provides the
LLM-driven browser control layer.

**Target advantage:** Adaptive to site structure changes; highest flexibility.
**Expected weakness:** Highest token cost; risk of hallucination; slowest per deal.
**Hallucination mitigation:** Every agent output is schema-validated before use.

---

## 2. Required Python Libraries
```
langgraph>=0.2          # Agent orchestration state machine
browser-use>=0.1.40     # LLM-controlled browser automation
langchain-openai>=0.1   # LLM interface (use OpenRouter-compatible endpoint)
pydantic>=2.0           # Strict output schema validation
httpx>=0.27             # For direct API calls within tool functions
asyncio                 # Concurrency
python-dotenv           # Environment management
```

**LLM for agent reasoning:** Use `claude-3-5-haiku` or `gpt-4o-mini` via OpenRouter.
This is the ORCHESTRATION LLM — distinct from the Gatekeeper LLM (Llama 3 8B).
Cost justification: agents make fewer, higher-stakes calls than the Gatekeeper.

---

## 3. LangGraph State Schema
```python
# All worker LLMs must implement this exact TypedDict
class PipelineState(TypedDict):
    deal: dict                        # Current deal from dataset
    search_attempts: int              # Counter: max 3 before NOT_FOUND
    candidates: list[dict]            # CandidateDocument list
    gatekeeper_results: list[dict]    # Gatekeeper verdicts
    downloaded_files: list[str]       # Local file paths
    pipeline_status: str              # Current status string
    api_calls_used: int               # Running total
    error_log: list[str]              # Non-fatal errors
    final_status: str                 # Terminal classification
```

---

## 4. The LangGraph Node Architecture
```
[START]
   │
   ▼
[exclusion_check_node]
   ├── already_processed → [log_node] → [END]
   └── active → [scout_node]
               │
               ▼
        [scout_node]          ← orchestrator decides WHERE to search
               │
               ├── found candidates → [gatekeeper_node]
               └── not found, attempts < 3 → [scout_node] (retry with different strategy)
               └── not found, attempts >= 3 → [log_node] → [END]
                                │
                                ▼
                       [gatekeeper_node]  ← calls Llama 3 8B via NIM
                               │
                               ├── DOWNLOAD → [fetcher_node]
                               └── SKIP → [log_node] → [END]
                                           │
                                           ▼
                                  [fetcher_node]
                                           │
                                           ├── success → [telemetry_node] → [END]
                                           └── fail → [fallback_node]
                                                            │
                                                            └── [telemetry_node] → [END]
```

---

## 5. The Scout Node — Orchestrator Agent

### Agent Definition

The Scout Agent has access to exactly these tools. No others.

**Tool 1: `search_courtlistener_api`**
```
Input: {company_name: str, filing_year: int, court: str, keyword: str}
Action: Calls CourtListener /api/rest/v3/docket-entries/ with server-side filters
Output: list[CandidateDocument] | empty list
API calls consumed: 1–3
```

**Tool 2: `search_claims_agent_browser`**  
```
Input: {company_name: str, claims_agent: str}
Action: Uses Browser-Use to navigate the specified claims agent site
Output: list[CandidateDocument] | empty list
```

**Tool 3: `search_courtlistener_text`**  
```
Input: {query: str}
Action: Calls CourtListener /api/rest/v3/search/ full-text endpoint
Output: list[CandidateDocument] | empty list
API calls consumed: 1
```

### Scout Orchestrator System Prompt
```
You are a Scout agent retrieving Chapter 11 bankruptcy documents.

DEAL: {deal_json}

YOUR GOAL: Find a CandidateDocument containing a First Day Declaration or DIP Motion
for this company. Return a list of CandidateDocument objects.

RULES:
1. Use search_courtlistener_api FIRST. It is fastest and most reliable.
2. Only use search_claims_agent_browser if CourtListener returns no results.
3. Only use search_courtlistener_text as a last resort.
4. Maximum 3 total tool calls. If no results after 3 calls, return empty list.
5. DO NOT fabricate document URLs. Only return URLs from tool results.
6. DO NOT call any tool not in your tool list.
7. Return ONLY valid JSON matching the CandidateDocument schema.

FORBIDDEN: Do not attempt to read PDFs. Do not invent docket entry IDs.
```

---

## 6. The Browser-Use Integration (Tool 2)

Browser-Use gives the agent natural language browser control. The worker LLM must
configure it with strict constraints to prevent hallucination-driven navigation.

**Browser-Use task prompt template:**
```
Navigate to the {claims_agent} case search page and find documents for 
"{company_name}" filed in {filing_year}.

Find documents with these titles (any one is sufficient):
- "First Day Declaration"
- "Declaration in Support of First Day Motions"  
- "DIP Motion" or "Debtor in Possession Financing Motion"

Extract ONLY: document title, filing date, PDF URL.
Do NOT click any download link.
Do NOT navigate away from the case page.
Return results as JSON only.
```

**Browser-Use configuration:**
```python
browser_config = BrowserConfig(
    headless=True,
    disable_security=False,      # Keep security; we want realistic browser
    extra_chromium_args=[
        "--disable-blink-features=AutomationControlled"
    ]
)
```

**Hallucination guardrail:** Validate every URL returned by Browser-Use against a
regex pattern. Reject any URL not matching known claims agent domains:
```
VALID_DOMAINS = [
    r"kroll\.com",
    r"cases\.stretto\.com", 
    r"dm\.epiq11\.com",
    r"storage\.courtlistener\.com"
]
```

---

## 7. The Gatekeeper Node

Identical interface to other worktrees. See `ARCHITECTURE_MASTER.md` §7.

Additional rule for Worktree C:
- If `gatekeeper_results` already contains a DOWNLOAD verdict for this deal,
  do not call the Gatekeeper again. Short-circuit to the Fetcher immediately.
- This prevents multiple Gatekeeper calls on retry loops.

---

## 8. The Fetcher Node

**Decision logic:**
```
IF candidate.source == "courtlistener":
    Use httpx direct download (no browser needed)
ELIF candidate.source in ["kroll", "stretto", "epiq"]:
    Use Browser-Use download (maintains session cookies)
```

Delegate to the same `fetcher.py` module used in other worktrees for consistency.

---

## 9. Anti-Hallucination Validation Layer

All three agent outputs must pass Pydantic validation before state update:
```python
# Scout output validation
class ScoutOutput(BaseModel):
    candidates: list[CandidateDocument]
    tool_calls_made: int = Field(ge=0, le=3)
    reasoning: str = Field(max_length=500)

# Gatekeeper output validation  
class GatekeeperOutput(BaseModel):
    verdict: Literal["DOWNLOAD", "SKIP"]
    score: float = Field(ge=0.0, le=1.0)
    reasoning: str = Field(max_length=200)
    token_count: int

# Fetcher output validation
class FetcherOutput(BaseModel):
    success: bool
    local_file_path: Optional[str]
    failure_reason: Optional[str]
    size_bytes: Optional[int] = Field(default=None, ge=0, le=52428800)
```

If validation fails → log `{"event": "validation_failure", "agent": "scout|gatekeeper|fetcher"}` → trigger retry or fallback.

---

## 10. Token Budget Enforcement

Worktree C uses two LLMs: the orchestrator (GPT-4o-mini/Haiku) and the Gatekeeper (Llama 3 8B).
```
Orchestrator budget per deal: 2,000 tokens max
Gatekeeper budget per call: 150 tokens max
Max orchestrator calls per deal: 3 (enforced in LangGraph conditional edge)
```

Track token usage in `PipelineState.api_calls_used`. If orchestrator budget exceeded:
abort current deal, log `{"event": "token_budget_exceeded", "deal_id": "..."}`, move to next deal.

---

## 11. Logging Events Specific to Worktree C
```json
{"event": "agent_tool_call", "agent": "scout", "tool": "search_courtlistener_api", "deal_id": "..."}
{"event": "agent_tool_result", "tool": "search_courtlistener_api", "candidates_found": 2, "deal_id": "..."}
{"event": "browser_use_task_start", "claims_agent": "Kroll", "deal_id": "..."}
{"event": "browser_use_task_complete", "urls_found": 1, "validation_passed": true, "deal_id": "..."}
{"event": "validation_failure", "agent": "scout", "error": "URL domain not in whitelist", "deal_id": "..."}
{"event": "langgraph_state_transition", "from": "scout_node", "to": "gatekeeper_node", "deal_id": "..."}
{"event": "token_budget_exceeded", "orchestrator_tokens": 2041, "deal_id": "..."}
{"event": "gatekeeper_decision", "verdict": "SKIP", "score": 0.31, "reasoning": "...", "deal_id": "..."}
```