"""Render Workflow tasks — one per subagent.

Each task runs a single subagent to completion on its own Render Workflow
instance, with its own retries, timeout, and compute plan. The orchestrator's
``task`` tool dispatches here via the Render SDK (see
``dispatch/workflow_subagent.py``).

The task *function names* (``research_agent``, ``editor_agent``) are how the
orchestrator addresses them: ``"<WORKFLOW_NAME>/research_agent"``. Keep them in
sync with the subagent names in ``agents/subagents.py``.
"""

from __future__ import annotations

from render_sdk import Retry, Workflows

from agents.subagents import EDITOR_AGENT, RESEARCH_AGENT, run_subagent_sync

app = Workflows(
    default_retry=Retry(max_retries=2, wait_duration_ms=1000, backoff_scaling=2),
    default_timeout=300,
    default_plan="standard",
)


@app.task(timeout_seconds=600)
def research_agent(task: str) -> str:
    """Research one subtopic on dedicated compute."""
    return run_subagent_sync(RESEARCH_AGENT, task)


@app.task(timeout_seconds=600)
def editor_agent(task: str) -> str:
    """Synthesize findings into a polished report body on dedicated compute."""
    return run_subagent_sync(EDITOR_AGENT, task)
