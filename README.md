# API Copilot – Local Eval & Tests

This project includes a deterministic eval harness and smoke tests that run without the LLM. These checks validate routing, health, RAG, and the write flow (create project + add cost items) against the mock ConTech API.

## Quick Start

- Activate your venv and ensure deps are installed (see `requirements.txt`).
- Start the primary mock API in a terminal:
  - `python -m uvicorn src.mock_api:app --port 8000 --reload`
- (Optional) Start the scheduler mock in another terminal:
  - `python -m uvicorn src.mock_api2:app --port 8001 --reload`

## Eval Harness (No‑LLM)

- Run the harness to print a JSON summary:
  - `python scripts/run_eval.py`
- Harness source: `scripts/run_eval.py:1`, `src/eval_harness.py:1`

Summary includes:
- Router selections for representative queries
- Health checks for selected APIs
- RAG result counts
- Write flow success (project created, two cost items added)

## Pytest Smoke Tests

- Install test deps: `python -m pip install -U pytest pytest-timeout`
- Run tests: `python -m pytest -q`
  - `tests/test_smoke.py:1`
  - `test_primary_smoke_only` passes when `src.mock_api` on `:8000` is running
  - `test_scheduler_optional` is skipped if `:8001` isn’t running, or passes if it is

## Agent Demo (LLM)

- Run the agent demo batch:
  - `python -u -m src.agent`
- Files used: `src/agent.py:1`, `src/tools.py:1`, `.env:1`

## Notes

- Do not commit secrets; `.env` is gitignored.
- Line endings are normalized via `.gitattributes`.
- The scheduler API is optional; tests skip gracefully if it’s not up.
