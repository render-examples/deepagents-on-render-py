"""Render Workflow tasks for the code review pipeline.

Each task wraps a LangChain agent factory: it creates the agent,
invokes it with the provided diff, and returns the result as a
JSON-serializable dict. Every run is traced to Postgres via the
``TracingCallbackHandler`` so the dashboard reflects live activity.
"""

from render_sdk import Workflows, Retry

from agents.security_reviewer import create_security_reviewer
from agents.style_reviewer import create_style_reviewer
from agents.logic_reviewer import create_logic_reviewer
from agents.orchestrator import create_orchestrator
from db.traces import TracingCallbackHandler

app = Workflows(
    default_retry=Retry(max_retries=2, wait_duration_ms=1000, backoff_scaling=2),
    default_timeout=300,
    default_plan="standard",
)


def _build_message(diff: str, repo: str | None, context: dict | None) -> str:
    """Prefix the diff with repo/context so the agent has full scope."""
    if not repo and not context:
        return diff

    header_lines = []
    if repo:
        header_lines.append(f"Repository: {repo}")
    if context:
        header_lines.append(f"Context: {context}")
    return "\n".join(header_lines) + "\n\n" + diff


def _run_agent(
    agent_factory,
    diff: str,
    agent_name: str,
    repo: str | None = None,
    context: dict | None = None,
) -> dict:
    """Create an agent, invoke it with a diff, return the final message content."""
    agent = agent_factory()
    handler = TracingCallbackHandler(
        agent_name=agent_name, meta={"repo": repo} if repo else None
    )
    message = _build_message(diff, repo, context)
    result = agent.invoke(
        {"messages": [{"role": "user", "content": message}]},
        config={"callbacks": [handler]},
    )
    return {"content": result["messages"][-1].content}


@app.task(plan="pro", timeout_seconds=600)
def orchestrate_review(diff: str, repo: str = "unknown", context: dict | None = None) -> dict:
    """Entry point: run the full code review pipeline.

    The orchestrator agent decides which reviewer agents to dispatch,
    fans them out as chained Render Workflow tasks, and synthesizes
    the results.
    """
    return _run_agent(
        create_orchestrator, diff, "orchestrator", repo=repo, context=context
    )


@app.task
def security_review(diff: str) -> dict:
    """Run a security-focused review of the diff."""
    return _run_agent(create_security_reviewer, diff, "security_reviewer")


@app.task
def style_review(diff: str) -> dict:
    """Run a style and readability review of the diff."""
    return _run_agent(create_style_reviewer, diff, "style_reviewer")


@app.task
def logic_review(diff: str) -> dict:
    """Run a logic and correctness review of the diff."""
    return _run_agent(create_logic_reviewer, diff, "logic_reviewer")
