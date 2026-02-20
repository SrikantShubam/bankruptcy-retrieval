# Worktree A - Pure CourtListener RECAP API Pipeline

This is Worktree A of a 3-way parallel architecture benchmark for an automated Chapter 11 bankruptcy document retrieval system. It implements a pure CourtListener RECAP API pipeline without any browser automation.

## Architecture

- **Primary Mechanism**: CourtListener REST API only, no browser
- **Target advantage**: Speed and auditability
- **Expected weakness**: Claims agents (Kroll, Epiq) not indexed in RECAP → coverage gaps

## Prerequisites

1. Python 3.8+
2. CourtListener API token (register at https://www.courtlistener.com/sign-in/)
3. Access to the shared bankruptcy-retrieval repository

## Installation

1. Install the required dependencies:
   ```bash
   pip install -r requirements.txt
   ```

2. Set up environment variables in the root `.env` file:
   ```
   COURTLISTENER_API_TOKEN=your_token_here
   OPENROUTER_API_KEY=your_key_here  # Optional, for Gatekeeper
   NVIDIA_NIM_API_KEY=your_key_here  # Optional, for Gatekeeper
   ```

## Directory Structure

```
worktree-a/
├── main.py            # Entrypoint
├── scout.py           # CourtListener API search logic
├── fetcher.py         # RECAP PDF streaming download
├── config.py          # Worktree-A-specific constants
├── requirements.txt   # Python dependencies
└── README.md          # This file
```

## Running the Pipeline

Execute the pipeline with:

```bash
python main.py
```

## Features

- **Rate limiting**: Respects CourtListener's 10 requests/second limit
- **Daily budget enforcement**: Hard stop at 4,800 requests (configurable)
- **Server-side filtering**: Uses CourtListener's powerful query parameters
- **Streaming downloads**: Efficient PDF download with size guards
- **Structured logging**: Comprehensive execution logs in JSONL format
- **Benchmarking**: Generates F1 scores and performance metrics

## Components

1. **Scout**: Searches CourtListener API in three phases:
   - Case lookup with docket search
   - Targeted docket entry search with keywords
   - RECAP document metadata extraction

2. **Gatekeeper**: LLM-based evaluator that decides whether to download documents

3. **Fetcher**: Downloads RECAP-hosted PDFs directly from CourtListener's S3 bucket

4. **Telemetry**: Logs execution events and computes benchmark metrics

## Configuration

Key configuration values can be adjusted in `config.py`:
- Court slug mappings
- Priority keywords for document search
- File size limits
- API rate limits

## Output

The pipeline generates:
- `logs/execution_log.jsonl`: Detailed execution events
- `logs/benchmark_report.json`: Performance metrics and F1 scores
- `downloads/`: Downloaded PDF documents organized by deal ID

## Compliance

- Respects CourtListener's rate limits (10 req/s)
- Implements daily budget (4,800 requests)
- Skips excluded deals before any API calls
- Never downloads PDFs to decide whether to download them