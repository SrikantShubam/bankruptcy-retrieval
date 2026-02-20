# Worktree C - Autonomous Agentic Pipeline

LangGraph-based multi-agent pipeline with tool-use for Chapter 11 bankruptcy document retrieval.

## Architecture

This worktree implements a LangGraph state machine with specialized agent nodes:

```
[START] → [exclusion_check] → (already_processed) → [log] → [END]
                       ↓ (active)
                  [scout] → (found) → [gatekeeper] → (download) → [fetcher] → (success) → [telemetry] → [END]
                       ↓ (retry/exhausted)         ↓ (skip)        ↓ (failed)
                      [scout]                      [log]          [fallback] → [telemetry] → [END]
```

## Key Components

### graph.py
- LangGraph StateGraph definition
- Defines all nodes and edges
- Implements routing logic for conditional flows

### nodes.py
- `exclusion_check_node`: Checks if deal is in excluded set
- `scout_node`: Scout agent searches for documents using tools
- `gatekeeper_node`: LLM evaluates candidates
- `fetcher_node`: Downloads approved documents
- `fallback_node`: Handles failed downloads
- `log_node`: Logs terminal state
- `telemetry_node`: Logs final telemetry

### tools.py
- `search_courtlistener_api`: CourtListener RECAP API search
- `search_claims_agent_browser`: Browser-Use powered claims agent search
- `search_courtlistener_fulltext`: Full-text search on CourtListener

### validators.py
- Pydantic schemas for all agent outputs
- URL domain validation (anti-hallucination)
- Strict validation before state updates

## Key Differences from Other Worktrees

| Feature | Worktree A | Worktree B | Worktree C |
|---------|------------|------------|------------|
| Mechanism | Pure RECAP API | Headless Browser | LangGraph Agents |
| Flexibility | Low | Medium | High |
| Token Cost | Low | Medium | High |
| Hallucination Risk | Low | Medium | High (mitigated by validation) |

## Configuration

Environment variables (see `.env`):
- `OPENROUTER_API_KEY`: For orchestrator LLM
- `NVIDIA_NIM_API_KEY`: For gatekeeper LLM
- `COURTLISTENER_API_TOKEN`: For CourtListener API
- `ORCHESTRATOR_MODEL`: LLM for Scout agent (default: llama-3.1-8b-instruct:free)
- `GATEKEEPER_MODEL`: LLM for Gatekeeper (default: llama-3.1-8b-instruct:free)

## Running

```bash
# Install dependencies
pip install -r requirements.txt

# Run pipeline
python main.py
```

## Validation Rules

1. **Graph First**: Graph structure is implemented before business logic
2. **Plain Async First**: Nodes are implemented as async functions first
3. **Pydantic Validation**: All agent outputs must pass Pydantic validation
4. **Token Budget**: Enforced in graph edges, not prompts
5. **Orchestrator/Gatekeeper Separation**: Different LLMs for different tasks

## Logging

- Execution logs: `logs/execution_log.jsonl`
- Benchmark report: `logs/benchmark_report.json`

## Anti-Hallucination

URLs from Browser-Use are validated against a whitelist:
- `kroll.com`
- `cases.stretto.com`
- `dm.epiq11.com`
- `storage.courtlistener.com`
- `ecf.*.uscourts.gov`
- `assets.kroll.com`
