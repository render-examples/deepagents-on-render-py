# Code Review Pipeline — LangChain + Render Workflows

A multi-agent code review pipeline built on **FastAPI**, **LangChain / LangGraph**, and **Render Workflows**, with every agent step traced to **Postgres** and surfaced in a live dashboard.

You `POST` a unified diff; an orchestrator agent decides which reviewers to run, fans them out as isolated Render Workflow tasks, and returns a structured `ReviewReport`.

## Overview

```
POST /reviews {diff, repo, context}
  → FastAPI validates input + checks API key
    → dispatches "code-review/orchestrate_review" on Render Workflows
      → Orchestrator agent (gpt-4o) analyzes the diff and decides scope
        → run_security_review  → security_review task  (own instance)
        → run_style_review     → style_review task     (own instance)
        → run_logic_review     → logic_review task      (own instance)
        → summarize_reviews    → summarizer agent       (in-process)
      → returns a structured ReviewReport (JSON)
  → every LLM + tool call written to Postgres via TracingCallbackHandler
  → dashboard at "/" renders traces and spans live
```

Key properties:

- **Agents are pure LangChain** — each reviewer is a factory returning a compiled `create_react_agent` graph with no Render dependency, so they're unit-testable with plain `pytest`.
- **Dual-mode execution** — the same agent runs in-process (summarizer) or as a distributed Render Workflow task (reviewers) for isolated, retryable, parallel compute.
- **The orchestrator is itself an agent** — it chooses which reviewers to dispatch based on diff content, rather than running a static DAG.
- **Observability built in** — `TracingCallbackHandler` records one `Trace` per run and one `Span` per LLM/tool call.
- **Secure by default in production** — `POST /reviews` and the trace APIs require an API key when `REVIEW_API_KEY` is set; diff size is bounded; agent tools are pure string/regex (no shell, filesystem, or git binary).

## Repository structure

```
langchain-workflows/
├── agents/                     # Pure LangChain — no Render dependency
│   ├── orchestrator.py         # Orchestrator agent + dispatch tools
│   ├── security_reviewer.py    # Security review agent factory
│   ├── style_reviewer.py       # Style/readability review agent factory
│   ├── logic_reviewer.py       # Logic/correctness review agent factory
│   ├── summarizer.py           # Summarizer agent (structured ReviewReport output)
│   └── tools/
│       ├── git.py              # In-memory unified-diff parsing tools
│       └── code_analysis.py    # Regex static-analysis tools (lang, patterns, imports)
├── workflows/                  # Render Workflows — task wrappers
│   ├── code_review/
│   │   ├── __init__.py         # Exports the Workflows app
│   │   └── tasks.py            # @app.task wrappers; wires in tracing
│   └── main.py                 # Workflows.from_workflows(...) + app.start()
├── api/                        # FastAPI trigger layer + dashboard
│   ├── app.py                  # App factory, lifespan (init_db), /health
│   ├── security.py             # require_api_key dependency (REVIEW_API_KEY)
│   ├── ui.py                   # Dashboard router + trace JSON APIs
│   ├── routes/reviews.py       # POST /reviews
│   ├── templates/dashboard.html
│   └── static/styles.css
├── db/                         # Postgres
│   ├── models.py               # SQLAlchemy Trace/Span models, engine, init_db
│   └── traces.py               # TracingCallbackHandler (LangChain callback)
├── models.py                   # Shared Pydantic models (ReviewRequest, ReviewReport, ...)
├── tests/                      # pytest suite for tools + models
├── requirements.txt
├── Dockerfile
├── docker-compose.yml          # Local API + Postgres
├── render.yaml                 # Blueprint for the web service + database
└── .env.example                # Documented environment variables
```

### Key files

| File | Responsibility |
|------|----------------|
| `api/routes/reviews.py` | Validates `ReviewRequest`, enforces auth, dispatches the orchestrator task. |
| `workflows/code_review/tasks.py` | Registers each agent as a Render task and attaches `TracingCallbackHandler`. |
| `agents/orchestrator.py` | The agent + tools that fan out reviewers and call the summarizer. |
| `db/traces.py` | Persists traces/spans for the dashboard. |
| `models.py` | The request/response contract (`ReviewReport` is the structured output). |

## Configuration

Copy `.env.example` to `.env` and fill in values.

| Variable | Required | Purpose |
|----------|----------|---------|
| `OPENAI_API_KEY` | Yes | Used by `ChatOpenAI` for all agents. |
| `DATABASE_URL` | Yes (prod) | Postgres connection string. Defaults to `postgresql://localhost:5432/langchain_workflows`. |
| `RENDER_API_KEY` | Yes (prod) | Lets the API and orchestrator trigger Render Workflow tasks. |
| `REVIEW_API_KEY` | Recommended | When set, `POST /reviews` and the trace APIs require it via `X-API-Key`. If unset, the API is open and logs a warning. |

## Quickstart

### Local (Python)

Requires Python 3.11+ and a running Postgres.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # then edit values

# Terminal 1 — FastAPI trigger layer + dashboard
export $(grep -v '^#' .env | xargs)
uvicorn api.app:app --reload --port 8000

# Terminal 2 — Render Workflows worker (registers + runs tasks)
export $(grep -v '^#' .env | xargs)
python -m workflows.main
```

Open http://localhost:8000 for the dashboard, or call the API directly:

```bash
curl -X POST http://localhost:8000/reviews \
  -H "content-type: application/json" \
  -H "x-api-key: $REVIEW_API_KEY" \
  -d '{"diff": "diff --git a/x.py b/x.py\n...", "repo": "owner/repo"}'
```

Run the tests:

```bash
pytest
```

### Docker

`docker-compose.yml` brings up the API and a Postgres instance together. Set `OPENAI_API_KEY` (and optionally `RENDER_API_KEY`, `REVIEW_API_KEY`) in your shell or a `.env` file first.

```bash
cp .env.example .env            # then edit values
docker compose up --build
```

- API + dashboard: http://localhost:8000
- Postgres: `localhost:5432` (`postgres` / `postgres`)

The Render Workflows worker (`python -m workflows.main`) is intentionally **not** containerized here — Workflows run on Render's managed infrastructure (see below). For fully local end-to-end runs, run the worker on the host as in the Local quickstart, pointing it at the same `DATABASE_URL`.

### Render deploy

Render Workflows and the web service deploy through two complementary mechanisms.

#### 1. Web service + database (Blueprint)

`render.yaml` provisions the FastAPI service and a managed Postgres database. From the [Render Dashboard](https://dashboard.render.com): **New → Blueprint**, point it at this repo, and Render syncs `render.yaml`. You'll be prompted for the `sync: false` secrets (`OPENAI_API_KEY`, `RENDER_API_KEY`, `REVIEW_API_KEY`); `DATABASE_URL` is wired automatically.

#### 2. Workflows service (Dashboard)

> Render Workflows are **not yet supported in Blueprints** — they must be created from the Dashboard.

In the Dashboard: **New → Workflow**, link this repo, then configure:

| Field | Value |
|-------|-------|
| Language | Python 3 |
| Root Directory | *(repo root — leave blank)* |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python -m workflows.main` |

Add the same environment variables (`OPENAI_API_KEY`, `DATABASE_URL`, `RENDER_API_KEY`) so reviewer tasks can call the LLM, write traces, and chain sub-tasks. Click **Deploy Workflow** — Render registers `orchestrate_review`, `security_review`, `style_review`, and `logic_review` during the build.

Once both are live, the web service triggers `code-review/orchestrate_review` on the Workflows service via the Render SDK.

## How it fits together

- **Triggering** — `RenderAsync().workflows.run_task("code-review/orchestrate_review", [diff, repo, context])` from the API and orchestrator tools.
- **Tracing** — every task wraps its agent invocation with `TracingCallbackHandler`, so traces appear identically whether the agent runs in-process or on a Workflow instance.
- **Structured output** — the summarizer binds `response_format=ReviewReport`, so the pipeline returns a validated report rather than free text.
```
