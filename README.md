# Vector

**Vector** is a full-stack job search platform that scrapes live job postings daily, indexes them for semantic search, and pairs users with a team of LLM agents that search, evaluate, and tailor application materials on their behalf.

A React SPA lets users browse and filter freshly scraped postings, track applications through a status pipeline, and chat with an AI assistant that can search the job database, recommend roles, tailor a resume to a specific posting, and generate company-specific interview prep — all backed by a FastAPI server and an Airflow-orchestrated ETL pipeline.

## Team

Built and maintained by ![Sean Berger](https://github.com/seanbrg) and ![Anna Ber](https://github.com/8anna8b6).


## Highlights

- **Daily job ingestion** — a Selenium-driven scraper pulls ~100 fresh LinkedIn postings a day across 50+ role/tech keywords, orchestrated as a 5-stage Airflow DAG (`scrape → extract → load Postgres → load ChromaDB → cleanup`).
- **LLM-based structured extraction** — Claude parses each raw job description into structured fields (role, seniority, required/nice-to-have skills, years of experience) with boilerplate-stripping preprocessing and JSON-repair retry logic.
- **Multi-vector semantic search** — every job is embedded as a full-text vector *and* per-field vectors (title, skills, company, location, description) in ChromaDB, queried with cosine similarity and metadata filters.
- **Multi-agent AI assistant** — a LangGraph orchestrator classifies user intent and delegates to four specialist agents, each exposed as a tool call:
  - **DB Agent** — structured + semantic job search, aggregate stats, skill trend queries
  - **Resume Agent** — resume upload/parsing, job-specific tailoring, gap analysis
  - **Job Advisor Agent** — career coaching, application strategy, course recommendations (web-search backed)
  - **Interview Agent** — finds real interview questions for a company/role and generates practice questions
- **Agent-as-a-judge evaluation** — every orchestrator response is scored asynchronously (0–100) across routing, completeness, accuracy, synthesis, and tone by a dedicated evaluator agent, with results persisted for offline analysis.
- **Full application lifecycle** — one-click apply, status tracking (`applied → screening → interview → offer/rejected/withdrawn`), and stats dashboards.
- **Auth** — email/password (bcrypt) plus Google and LinkedIn OAuth, backed by JWTs.

## Architecture

```
                    ┌─────────────────────────────────────────────┐
                    │              Airflow DAG (daily)             │
                    │  scrape → extract → load PG → load Chroma    │
                    └───────────────┬───────────────────────────────┘
                                    │
         Selenium (undetected-chromedriver)   Claude (structured extraction)
                                    │
                    ┌───────────────▼───────────────┐
                    │   PostgreSQL      ChromaDB      │
                    │  (structured)   (embeddings)    │
                    └───────────────┬───────────────┘
                                    │
                    ┌───────────────▼───────────────┐
                    │           FastAPI server         │
                    │  auth · jobs · resumes ·         │
                    │  applications · stats · agents   │
                    └───────────────┬───────────────┘
                                    │  SSE streaming
                    ┌───────────────▼───────────────┐
                    │        LangGraph Orchestrator    │
                    │   (Claude, tool-calling router)  │
                    └───┬───────┬───────┬───────┬────┘
                        │       │       │       │
                    DB Agent  Resume  Advisor  Interview
                              Agent    Agent     Agent
                                    │
                          Evaluator Agent (async, LLM-as-judge)
                                    │
                    ┌───────────────▼───────────────┐
                    │      React + TypeScript SPA      │
                    └───────────────────────────────┘
```

## Tech stack

| Layer | Technology |
|---|---|
| Frontend | React 18, TypeScript, Vite, React Router, Axios, Recharts |
| Backend API | FastAPI, Uvicorn, PostgreSQL, JWT auth (python-jose, bcrypt) |
| Agents | LangGraph (`StateGraph`), LangChain, Claude (Anthropic API) |
| Vector search | ChromaDB (cosine similarity, multi-vector-per-document) |
| Scraping | Selenium + `undetected-chromedriver` |
| Orchestration | Apache Airflow (`LocalExecutor`) |
| Deployment | Docker / docker-compose |

## Repository layout

```
client/                  React + TypeScript SPA (Vite)
  src/pages/              JobsPage, ApplicationsPage, ProfilePage, StatsPage, AuthPage, ...
  src/components/         AgentChat (SSE streaming chat), JobCard, JobDrawer, ProtectedRoute
  src/api/                Axios clients per domain (auth, jobs, resumes, applications, stats)

server/
  main.py                 FastAPI app entrypoint
  features/                One router per domain: auth, jobs, resumes, applications, agents, stats
  agents/
    orchestrator/          Intent classification + tool-calling router (LangGraph)
    data/                  DB Agent — structured & semantic job queries
    resume/                Resume Agent — upload, tailor, gap analysis
    advisor/                Job Advisor Agent — career coaching, course recs
    interview/              Interview Agent — company-specific question search & generation
    eval/                   Evaluator Agent — LLM-as-judge scoring of orchestrator responses
  db/
    postgres.py             Schema + all SQL (users, jobs, resumes, applications, agent_evaluations)
    chroma.py                Multi-vector embedding, upsert, and semantic search
    embeddings.py             Embedding generation
  pipeline/
    scraper/                 Selenium scraper (LinkedIn)
    extractor.py              Claude-based structured field extraction
    core.py                    scrape → extract → load orchestration used by the DAG
  tests/                    Pytest suite (agents, jobs, resumes)

dags/scraper_dag.py       Airflow DAG definition (daily schedule)
scripts/                  Local dev helpers (run.sh, runner.py, setup_models.sh)
docker-compose.yml        Postgres + Airflow (scheduler/webserver) services
Dockerfile                Airflow image with headless Chrome baked in for scraping
```

## Getting started

### Prerequisites

- Python 3.11+, Node 18+, PostgreSQL, Docker (for Airflow)
- An Anthropic API key

### 1. Clone and configure

```bash
git clone <repo-url>
cd vector-ai-career-advisor
cp .env.example .env   # fill in DB credentials, ANTHROPIC_API_KEY, etc.
```

### 2. Install dependencies

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt      # or requirements-windows.txt on Windows

cd client && npm install && cd ..
```

### 3. Run the app locally

```bash
./scripts/run.sh
```

This starts the FastAPI server on `http://localhost:8000` and the Vite dev server on `http://localhost:5173`. On startup, the API creates all required PostgreSQL tables automatically.

### 4. Run the scraping pipeline

The pipeline normally runs on Airflow's daily schedule, but can be run standalone for local testing:

```bash
docker-compose up          # Postgres + Airflow scheduler/webserver on :8080
# or, bypass Airflow entirely for a single local run:
PYTHONPATH=. .venv/bin/python scripts/runner.py
```

### 5. Run tests

```bash
PYTHONPATH=. .venv/bin/pytest server/tests/
```

## Configuration

All configuration lives in `.env` (see `.env.example`):

| Variable | Purpose |
|---|---|
| `DB_HOST` / `DB_PORT` / `DB_NAME` / `DB_USER` / `DB_PASSWORD` | PostgreSQL connection |
| `ANTHROPIC_API_KEY` | Claude API access |
| `ANTHROPIC_MODEL` | Model used for job extraction and specialist agents |
| `ORCHESTRATOR_MODEL` / `EVALUATION_MODEL` | Models for the router agent and the LLM-as-judge evaluator |
| `CHROMA_DIR` / `CHROMA_COLLECTION` | ChromaDB persistence path and collection name |
| `CHROME_VERSION` | Chrome version pin for the scraper's headless driver |
| `DAILY_TARGET` | Max number of jobs the scraper ingests per run |

## Deployment

The FastAPI server ships as a Docker container (`Dockerfile`) and is deployed to EC2 behind Docker; `docker-compose.yml` orchestrates PostgreSQL and the Airflow scheduler/webserver that run the daily scrape DAG.

## License

All rights reserved. See [LICENSE](LICENSE).
