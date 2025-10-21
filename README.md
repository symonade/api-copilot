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

## Features Coming Soon (UI)

- Streamlit panel (right-side expander, cards):
  - `streamlit run streamlit_app.py`
- FastAPI page (served by mock API):
  - Start API: `python -m uvicorn src.mock_api:app --reload --port 8000`
  - Visit: `http://localhost:8000/features`
- CLI banner (env-gated):
  - In PowerShell: `$env:SHOW_FEATURES="1"; python -u -m src.agent`
  - In bash: `export SHOW_FEATURES=1 && python -u -m src.agent`
  - Set to `0` (or unset) to keep banner off.

## Local dev with .env.sample → .env

- Copy `.env.sample` to `.env` and adjust values as needed. Do not commit secrets.
- Ensure `PRIMARY_API_BASE_URL` points to your local mock (`http://localhost:8000`).

## Quick start on Render

- Push this repo to GitHub, then on Render choose “New → Blueprint” and select your repo.
- Render uses `render.yaml` to build and run the service.
- Set these environment variables in Render:
  - `GOOGLE_API_KEY` (required)
  - `PUBLIC_CHAT_API_KEY` (optional, to gate `/chat`)
  - `ALLOWED_ORIGINS` (comma-separated origins for CORS, e.g., your Render URL)
- After deploy, open your Render URL. Endpoints:
  - `/` minimal chat UI
  - `/chat` HTMX handler (POST)
  - `/mock/status` mock API status
  - `/healthz` application health


## Notes

- Do not commit secrets; `.env` is gitignored.
- Line endings are normalized via `.gitattributes`.
- The scheduler API is optional; tests skip gracefully if it’s not up.
