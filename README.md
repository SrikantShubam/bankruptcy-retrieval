# Worktree B - Anti-Detect Clams Agent Scraper

This folder contains the implementation for Worktree B of the bankruptcy document retrieval pipeline. It uses Camoufox and nodriver to scrape claims agent domains while evading bot mitigation (Cloudflare).

## Pipeline Architecture
1. **Configured Domains:** Kroll (`kroll.com`), Stretto (`cases.stretto.com`), Epiq (`dm.epiq11.com`)
2. **Main browser:** `AsyncCamoufox` (patched Firefox) -> retains session cookies internally to pass IP reputation.
3. **Fallback browser:** `nodriver` (Chromium CDP), used exclusively as a secondary attempt for aggressive Cloudflare instances on Epiq.
4. **Scout Flow:** Automatically bypasses JS challenges, filters target documents by keyword, extracts metadata.
5. **Gatekeeper:** Shared LLM interface to judge candidate relevance.
6. **Fetcher:** Playwright context download interception, backed by an `httpx` stream utilizing retained cookies.
7. **Telemetry:** Native integration with `execution_log.jsonl` matching F1 evaluation demands.

## Setup
Ensure Python 3.10+ and install requirements:
```bash
pip install -r requirements.txt
playwright install firefox
```

*Note: Worktree A and C are maintained separately per architecture rules.*
