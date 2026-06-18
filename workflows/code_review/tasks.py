"""Render Workflow tasks for the code review pipeline.

Each task wraps a LangChain agent factory: it creates the agent,
invokes it with the provided diff, and returns the result as a
JSON-serializable dict.
"""

from render_sdk import Workflows, Retry

from agents.security_reviewer import create_security_reviewer
from agents.style_reviewer import create_style_reviewer
from agents.logic_reviewer import create_logic_reviewer
from agents.orchestrator import create_orchestrator

app = Workflows(
    default_retry=Retry(max_retries=2, wait_duration_ms=1000, backoff_scaling=2),
    default_timeout=300,
    default_plan="standard",
)


def _run_agent(agent_factory, diff: str) -> dict:
    """Create an agent, invoke it with a diff, return the final message content."""
    agent = agent_factory()
    result = agent.invoke({"messages": [{"role": "user", "content": diff}]})
    return {"content": result["messages"][-1].content}


@app.task(plan="pro", timeout_seconds=600)
def orchestrate_review(diff: str) -> dict:
    """Entry point: run the full code review pipeline.

    The orchestrator agent decides which reviewer agents to dispatch,
    fans them out as chained Render Workflow tasks, and synthesizes
    the results.
    """
    return _run_agent(create_orchestrator, diff)


@app.task
def security_review(diff: str) -> dict:
    """Run a security-focused review of the diff."""
    return _run_agent(create_security_reviewer, diff)


@app.task
def style_review(diff: str) -> dict:
    """Run a style and readability review of the diff."""
    return _run_agent(create_style_reviewer, diff)


@app.task
def logic_review(diff: str) -> dict:
    """Run a logic and correctness review of the diff."""
    return _run_agent(create_logic_reviewer, diff)
