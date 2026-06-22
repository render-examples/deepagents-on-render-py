# Deep Agents on Render (Python)

A production scaffold for running [LangChain **Deep Agents**](https://docs.langchain.com/oss/python/deepagents/overview) on Render, with the two things Deep Agents doesn't give you out of the box:

- **Durable state** — every step of every run is checkpointed to **Render Postgres** via LangGraph's `AsyncPostgresSaver`. Runs survive restarts and work across replicas.
- **Distributed execution** — when the orchestrator spawns a subagent (the built-in `task` tool), it runs as its own **Render Workflow** task — dedicated compute, retries, timeout, and plan — instead of in-process.

It also wires up **human-in-the-loop**: the agent pauses for approval before publishing, holds its state in Postgres, and resumes on a later request — even if the process restarted in between.

> **The example domain is not the point.** It's a small *research report generator* (an orchestrator + a `research-agent` + an `editor-agent`) that exists only to prove the scaffold works. Replace the agents in `agents/` with your own; you shouldn't need to touch the infrastructure code.

## How it works

```
POST /run/research {topic}
  → FastAPI validates input + checks API key
    → Orchestrator deep agent (Postgres checkpointer, thread_id)
        → task(research-agent)  ─┐
        → task(research-agent)   ├─ each dispatched as a Render Workflow task
        → task(editor-agent)    ─┘   (its own instance / retries / plan)
        → publish_report(...)    ── human-in-the-loop interrupt ──► pauses
  → returns {status: "interrupted", action_requests: [...]}

POST /resume/{thread_id} {decisions: [{type: "approve"}]}
  → resumes from the Postgres checkpoint, runs publish_report
  → report persisted to Postgres; returns {status: "completed", report}
```

The integration hook is small and lives in one file: [`dispatch/workflow_subagent.py`](dispatch/workflow_subagent.py) registers each subagent as a `CompiledSubAgent` whose runnable dispatches to `RenderAsync().workflows.run_task(...)`. When `RENDER_API_KEY` is not set (local dev, tests), it transparently falls back to running the subagent in-process — so the same graph runs end-to-end with zero infrastructure.

## Repository structure

```
deepagents-on-render-py/
├── agents/                     # Pure LangChain — no Render dependency
│   ├── model.py                # Provider selection (Anthropic / OpenAI)
│   ├── subagents.py            # Subagent specs + in-process runner (reused by Workflows)
│   ├── orchestrator.py         # create_deep_agent: subagents + interrupt_on + checkpointer
│   └── tools.py                # publish_report (the human-in-the-loop gated tool)
├── dispatch/
│   └── workflow_subagent.py    # CompiledSubAgent that routes task() → Render Workflows
├── checkpoint/
│   └── postgres.py             # Sized connection pool + AsyncPostgresSaver
├── db/
│   └── reports.py              # Published-report persistence (shares the pool)
├── api/
│   ├── app.py                  # FastAPI app + lifespan (pool → checkpointer → agent)
│   ├── security.py             # API-key auth (X-API-Key)
│   └── routes/runs.py          # /run, /resume, /runs, /reports
├── workflows/                  # Render Workflows — one task per subagent
│   ├── research/tasks.py       # @app.task research_agent, editor_agent
│   └── main.py                 # Workflows.from_workflows(...) + app.start()
├── models.py                   # Pydantic request/response contract
├── tests/                      # pytest suite (dispatch + API mapping)
├── render.yaml                 # Blueprint: web service + Postgres
├── Dockerfile / docker-compose.yml
└── .env.example
```

## Configuration

Copy `.env.example` to `.env` and fill in values. See that file for the full list; the essentials:

| Variable | Required | Purpose |
|----------|----------|---------|
| `ANTHROPIC_API_KEY` / `OPENAI_API_KEY` | One of them | Model provider. Anthropic wins if both set (override with `LLM_PROVIDER`). |
| `DATABASE_URL` | Yes | Postgres for the checkpointer + report store. Injected by Render in prod. |
| `DB_POOL_MAX_SIZE` | Recommended | Pool size — set to your Postgres plan's connection limit / number of instances. |
| `RENDER_API_KEY` | Prod | Enables Workflow dispatch. When unset, subagents run in-process. |
| `WORKFLOW_NAME` | Prod | Name of your Dashboard Workflow; tasks are addressed as `<WORKFLOW_NAME>/research_agent`. |
| `API_KEY` | Recommended | When set, all endpoints require it via `X-API-Key`. |

## Quickstart (local)

Requires Python 3.11+ and a running Postgres.

```bash
python -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env            # set ANTHROPIC_API_KEY or OPENAI_API_KEY + DATABASE_URL

export $(grep -v '^#' .env | xargs)
uvicorn api.app:app --reload --port 8000
```

With `RENDER_API_KEY` unset, subagents run in-process — no Workflows worker needed. Trigger a run:

```bash
# 1. Start a run — it pauses for approval before publishing.
curl -X POST http://localhost:8000/run/research \
  -H 'content-type: application/json' -H "x-api-key: $API_KEY" \
  -d '{"topic": "the state of solid-state batteries"}'
# → {"thread_id": "...", "status": "interrupted", "action_requests": [{"name": "publish_report", ...}]}

# 2. Approve it — resumes from the checkpoint and publishes.
curl -X POST http://localhost:8000/resume/<thread_id> \
  -H 'content-type: application/json' -H "x-api-key: $API_KEY" \
  -d '{"decisions": [{"type": "approve"}]}'
# → {"thread_id": "...", "status": "completed", "report": {...}}
```

To verify durability (R3): stop the server after step 1 and start it again before step 2 — `/resume` still works, because the interrupted state lives in Postgres.

Run the tests:

```bash
pytest
```

### Docker

`docker-compose.yml` brings up the API + Postgres together (subagents in-process):

```bash
cp .env.example .env            # set a model key
docker compose up --build       # API at http://localhost:8000
```

## Deploy to Render

Render Workflows and the web service deploy through two complementary mechanisms.

### 1. Web service + database (Blueprint)

`render.yaml` provisions the FastAPI service and a managed Postgres database. In the [Render Dashboard](https://dashboard.render.com): **New → Blueprint**, point it at this repo, and Render syncs `render.yaml`. You'll be prompted for the `sync: false` secrets (`ANTHROPIC_API_KEY`/`OPENAI_API_KEY`, `RENDER_API_KEY`, `API_KEY`); `DATABASE_URL` is wired automatically.

### 2. Workflows service (Dashboard)

> Render Workflows are **not yet supported in Blueprints** — create the Workflow from the Dashboard.

In the Dashboard: **New → Workflow**, link this repo, then configure:

| Field | Value |
|-------|-------|
| Name | `deep-agents` *(must match `WORKFLOW_NAME`)* |
| Language | Python 3 |
| Build Command | `pip install -r requirements.txt` |
| Start Command | `python -m workflows.main` |

Add the same model key and `DATABASE_URL`. Click **Deploy Workflow** — Render registers `research_agent` and `editor_agent` during the build. Once both services are live, set `RENDER_API_KEY` on the web service so the orchestrator dispatches subagents to `deep-agents/research_agent` and `deep-agents/editor_agent`.

**Pool sizing (R4):** set `DB_POOL_MAX_SIZE` so that `web instances + workflow instances` × `DB_POOL_MAX_SIZE` stays under your Postgres plan's connection limit.

## Add your own agent

This scaffold is designed so you replace the example agents without touching infrastructure:

1. **Define a subagent** in `agents/subagents.py` — a `SubAgentSpec` with a name, description, system prompt, and optional tools.
2. **Register it** in `agents/orchestrator.py`: add `workflow_subagent(MY_AGENT)` to the `subagents=[...]` list and mention it in the system prompt.
3. **Expose it as a Workflow task** in `workflows/research/tasks.py` (or a new `workflows/<domain>/`): a one-line `@app.task` that calls `run_subagent_sync(MY_AGENT, task)`. The task function name must match the subagent name with underscores (`my-agent` → `my_agent`).
4. **Customize the gate** (optional): change `interrupt_on` in `agents/orchestrator.py` to pause on whichever tools you want a human to approve.

Everything else — checkpointing, pooling, dispatch, the API, auth — stays the same.

## How the requirements are met

| # | Requirement | Where |
|---|-------------|-------|
| R1 | Postgres checkpointing via `AsyncPostgresSaver` from `DATABASE_URL` | `checkpoint/postgres.py`, `api/app.py` |
| R2 | Subagent dispatch via Render Workflows, not in-process | `dispatch/workflow_subagent.py`, `workflows/research/tasks.py` |
| R3 | Human-in-the-loop with `interrupt_on`; state in Postgres; resume after restart | `agents/orchestrator.py`, `api/routes/runs.py` |
| R4 | Connection pooling sized to the plan | `checkpoint/postgres.py` (`DB_POOL_MAX_SIZE`) |
| R5 | `render.yaml` provisions web + Postgres (Workflows via Dashboard) | `render.yaml` |
| R6 | 1 orchestrator + 2 subagents; `POST /run/{agent}` returns a structured result | `agents/`, `api/routes/runs.py`, `models.py` |
| R7 | Fork-and-customize without touching infra | `agents/` + "Add your own agent" above |
| R8 | `.env.example` documents all variables | `.env.example` |
| R9 | README: local dev, Render deploy, add-your-own-agent | this file |
