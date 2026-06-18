# LangChain + Render Workflows: Code Review Multi-Agent Pipeline

A production-ready demo of multi-agent workloads on FastAPI, LangChain, and Render Workflows — with traces written to Postgres.

## Use Case

A code review pipeline that receives a PR diff and produces a structured review report. An orchestrator agent analyzes the diff and dispatches specialized reviewer agents in parallel on isolated Render Workflow instances.

```
POST /reviews {diff, repo}
  → FastAPI dispatches orchestrator task on Render Workflows
    → Orchestrator agent (LangChain) analyzes the diff
    → Orchestrator tools dispatch sub-agent tasks in parallel:
        → security_review task (own instance, own agent)
        → style_review task (own instance, own agent)
        → logic_review task (own instance, own agent)
    → Orchestrator receives results, runs summarizer in-process
    → Returns structured ReviewReport
  → All steps traced to Postgres via middleware
```

## Architecture Decisions

### 1. Agents are pure LangChain

Agent definitions are factory functions that return a compiled `create_agent` graph. They have no Render SDK dependency and are independently testable with plain `pytest`.

```python
# agents/security.py
from langchain.agents import create_agent

def create_security_reviewer():
    return create_agent(
        model="openai:gpt-4o",
        tools=[scan_secrets, check_dependencies],
        system_prompt="You are a security code reviewer...",
    )
```

### 2. A thin `agent_task` helper bridges LangChain and Render Workflows

A small utility takes an agent factory and registers it as a Render Workflow task, while also exposing an in-process callable. One definition, two calling modes.

```python
# workflows/tasks.py
from render_sdk import Workflows

app = Workflows()

@app.task(plan="pro", timeout_seconds=300)
def security_review(diff: str, context: dict) -> dict:
    agent = create_security_reviewer()
    result = agent.invoke({"messages": [{"role": "user", "content": diff}]})
    return serialize_review(result)
```

Agents can be called:
- **In-process** — directly invoking the agent factory (fast, no network hop, good for lightweight steps like summarization)
- **As a Render Workflow task** — dispatched via the SDK client (isolated compute, retries, timeouts, good for heavy/parallel work)

### 3. The orchestrator is itself a LangChain agent

The orchestrator is not a hard-coded pipeline — it's a LangChain agent whose tools dispatch sub-agents as Render Workflow tasks. The agent decides which reviewers to invoke based on the diff content.

```python
# agents/orchestrator.py
@tool
async def run_security_review(diff: str) -> str:
    """Dispatch a security review on dedicated compute."""
    render = RenderAsync()
    result = await render.workflows.run_task("code-review/security_review", [diff])
    return json.dumps(result.results)

orchestrator = create_agent(
    model="openai:gpt-4o",
    tools=[run_security_review, run_style_review, run_logic_review],
    system_prompt="You coordinate code reviews. Analyze the diff and dispatch...",
)
```

### 4. Tracing is a LangChain middleware

A custom `TracingMiddleware` writes structured trace data to Postgres via `before_agent`, `after_model`, `wrap_tool_call`, and `after_agent` hooks. This works identically whether the agent runs in-process or inside a Render Workflow task.

### 5. FastAPI is a thin trigger layer

The API surface is minimal. `POST /reviews` accepts a diff, dispatches the orchestrator as a Render Workflow task, and returns/streams the result.

## Repo Structure

```
langchain-workflows/
├── agents/                    # Pure LangChain — no Render dependency
│   ├── orchestrator.py        # LangChain agent that dispatches sub-agents
│   ├── security_reviewer.py            # Security review agent factory
│   ├── style_reviewer.py               # Style review agent factory
│   ├── logic_reviewer.py               # Logic review agent factory
│   ├── summarizer.py          # Summarizer agent (runs in-process)
│   └── tools/                 # Shared tool definitions
│       ├── git.py             # Diff parsing, file extraction
│       └── code_analysis.py   # Static analysis helpers
├── workflows/                 # Render Workflows — task wrappers
│   ├── code_review/           # Code review workflow domain
│   │   ├── __init__.py        # Exports the Workflows app
│   │   └── tasks.py           # @app.task wrappers for each agent
│   └── main.py                # from_workflows(...), app.start()
├── api/                       # FastAPI
│   ├── app.py                 # FastAPI application
│   └── routes/
│       └── reviews.py         # POST /reviews endpoint
├── db/                        # Postgres
│   ├── models.py              # SQLAlchemy/Pydantic models for traces
│   └── traces.py              # TracingMiddleware implementation
├── models.py                  # Shared Pydantic models (ReviewResult, etc.)
├── requirements.txt
└── README.md
```

## Key Patterns Demonstrated

- **Agents deciding what to run** — the orchestrator is an LLM that chooses which reviewers to dispatch, not a static DAG
- **Parallel distributed execution** — fan-out via Render Workflow tasks with `asyncio.gather`
- **Mixed in-process and distributed** — summarizer runs in-process within the orchestrator's task; reviewers get their own instances
- **Durable execution** — automatic retries, configurable timeouts, isolated compute per agent
- **Observability** — every agent step traced to Postgres via LangChain middleware
- **Dual-mode agents** — same agent definition callable in-process or as a distributed task

## Notes
- We will want a quickstart guide on how to bring over existing langchain agents
- We will want to expand tools and potentially introduce API key to pull context from around the changes (ie fetch file contents from github)
