# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

**Vector** is a job board RAG system — a full-stack web app that scrapes LinkedIn jobs, embeds them into ChromaDB for semantic search, and uses multi-agent AI (Claude + LangGraph) to help users find and apply to jobs.

## Commands

### Frontend (`/client`)
```bash
npm run dev        # Start Vite dev server on port 5173
npm run build      # Type-check and bundle
npm run preview    # Serve production build
```

### Backend
```bash
cd server/web && ../../.venv/bin/uvicorn main:app --reload --port 8000   # Start FastAPI server
```
(`server/main.py` has no `__main__` block — it's an ASGI app module, always run through `uvicorn`, not `python`. `scripts/run.sh` runs this plus the frontend together.)

### Full stack
```bash
./scripts/setup.sh   # First time: DB tables, vector_agent role, docker compose build, npm install
docker compose up     # PostgreSQL + FastAPI server + MCP server + Airflow (scheduler/webserver)
```
The frontend isn't containerized — run it separately (`cd client && npm run dev`).

### Tests
```bash
PYTHONPATH=. .venv/bin/pytest server/tests/    # Run backend tests
```

## Architecture

### Data flow
1. **Scraping:** Airflow DAG → Selenium scrapes LinkedIn → raw job stubs
2. **Extraction:** LLM parses descriptions → structured fields (skills, seniority, requirements)
3. **Storage:** PostgreSQL (structured) + ChromaDB (local embedding model, `chromadb`'s built-in `DefaultEmbeddingFunction`)
4. **User queries:** React → FastAPI → Orchestrator agent → specialist agents → tools → DB (some tool calls go out to the MCP server, see below)

### Backend (`/server`)

- **`web/`** — the FastAPI app; its own container (`Dockerfile.server`, service `server`)
  - **`main.py`** — app entrypoint (ASGI module, run via `uvicorn main:app`)
  - **`core/`** — config, JWT auth/security, exception handlers, logging
  - **`features/`** — routers, one subdirectory per domain: `auth/`, `jobs/`, `resumes/`, `applications/`, `agents/`, `stats/`
  - **`agents/`** — multi-agent orchestration via LangGraph `StateGraph`
- **`db/`** — shared by `web` and the ETL pipeline, not containerized separately
  - **`postgres.py`** — all SQL (users, jobs, resumes, applications, agent_evaluations)
  - **`chroma.py`** — vector search against ChromaDB
  - **`embeddings.py`** — embedding generation (local ONNX model via ChromaDB, no external service)
- **`mcp/`** — MCP server: the agent runtime's read-only DB access, over its own `vector_agent` Postgres role (`scripts/sql/create_agent_role.sql`) — its own container (service `mcp-db`), reachable only from other containers, never from the host or imported into `web`
- **`etl/`** — scrape → extract → insert → embed pipeline, plus `etl/dags/` (Airflow DAG definitions) — its own container image (`Dockerfile.airflow`, services `airflow-init`/`scheduler`/`webserver`)
- **`logs/`** — Airflow logs (mounted into the Airflow containers) and per-user chat session logs (written by `web/core/logging.py`)
- **`tests/`** — pytest suite, layout mirrors the above (`tests/agents`, `tests/features`, `tests/mcp`)

### Agent system (`/server/web/agents`)

The orchestrator (`orchestrator.py`) classifies user intent and routes to specialist agents, each exposed as a `@tool`:
- `db_agent.py` — structured DB queries, job search/stats, and (via `agents/tools/mcp_client.py`) the MCP-backed tools: user-scoped applications and freeform read-only SQL
- `resume_agent.py` — resume upload, tailoring, gap analysis
- `job_advisor_agent.py` — job recommendations
- `interview_agent.py` — company-specific interview question search/generation
- `evaluator_agent.py` — LLM-as-judge scoring of orchestrator responses

`conversation_history` is shared across agents as a `ContextVar` (no threading needed). Agent system prompts live in each agent's `prompt.py`.

### Frontend (`/client/src`)

React 18 + TypeScript + Vite. Routes are protected via OAuth token handling. Key components: `AgentChat` (streaming agent responses), `ProtectedRoute`. API calls go through Axios to the FastAPI backend (proxied by Vite in dev — see `client/vite.config.ts`).

### Configuration

All secrets and model names are in `.env` (copy from `.env.example`): PostgreSQL connection, Anthropic API key, ChromaDB settings, and the MCP server's `AGENT_DB_PASSWORD`/`AGENT_TOKEN_SECRET`/`MCP_URL`.
