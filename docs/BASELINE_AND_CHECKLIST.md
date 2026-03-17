# Worktree D Baseline And Checklist

## Current Baseline (from Worktree C)
- Full run (68 deals):
  - `F1=0.8406`
  - `Precision=0.9355`
  - `Recall=0.7632`
  - `TP=29`, `FP=2`, `FN=9`, `TN=23`
  - `infra_failed=0`

## Known FP / FN Cluster
- FP:
  - `iheartmedia-2023`
  - `intelsat-2023`
- FN:
  - `bed-bath-beyond-2023`
  - `purdue-pharma-2019`
  - `mallinckrodt-2023`
  - `icon-aircraft-2023`
  - `ligado-networks-2024`
  - `lannett-2023`
  - `chicken-soup-2023`
  - `core-scientific-2022`
  - `rackspace-2023`

## Required Environment Variables
- `COURTLISTENER_API_TOKEN`
- `OPENROUTER_API_KEY` (if using OpenRouter for agent reasoning)
- `NVIDIA_NIM_API_KEY` (if using NIM path)

## Required Run Commands
- Smoke run:
  - `python main.py --standard-test`
- Full run:
  - `python main.py`

## Day-1 Worktree D Checklist
1. Create isolated D pipeline entrypoint and graph/orchestrator.
2. Implement planner/retriever/verifier/decision modules.
3. Reuse data + telemetry schema compatibility from C.
4. Add infra preflight and explicit `INFRA_FAILED` handling.
5. Run 10-case smoke and confirm `infra_failed=0` under healthy network.
6. Run full benchmark and produce FN/FP list.
7. Compare D metrics against C baseline above.

## Non-Negotiables
- Do not modify A/B/C behavior.
- Do not classify infra/network failures as retrieval misses.
- Do not download before decision/verification.

