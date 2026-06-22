"""Route Deep Agents' ``task`` tool to Render Workflows.

This is the heart of the integration. Deep Agents ships a built-in ``task``
tool that spawns subagents. By registering each subagent as a
``CompiledSubAgent`` whose ``runnable`` we control, we intercept that spawn:
instead of running the subagent in the orchestrator's process, we dispatch it
to a dedicated Render Workflow task — its own instance, retries, timeout, and
compute plan.

The runnable contract (see ``deepagents.middleware.subagents``):

* It is invoked with a state dict whose ``messages`` key holds a single
  ``HumanMessage`` containing the task description.
* It must return a dict containing a ``messages`` key. The last AIMessage's
  text is handed back to the orchestrator as the subagent's result.

When ``RENDER_API_KEY`` is not set (local dev, tests), we transparently fall
back to running the subagent in-process so the example works with zero infra.
"""

from __future__ import annotations

import json
import logging
import os

from deepagents import CompiledSubAgent
from langchain_core.messages import AIMessage
from langchain_core.runnables import RunnableLambda

from agents.subagents import SubAgentSpec, run_subagent_async

logger = logging.getLogger(__name__)

# Render Workflow service name. Must match the name of the Workflow you create
# in the Render Dashboard (New > Workflow). Tasks are addressed as
# "<WORKFLOW_NAME>/<task_function_name>".
WORKFLOW_NAME = os.environ.get("WORKFLOW_NAME", "deep-agents")


def workflows_enabled() -> bool:
    """Dispatch to Render Workflows only when an API key is present.

    Lets the same agent graph run end-to-end locally (in-process subagents)
    and in production (distributed Workflow tasks) with no code change.
    """
    if os.environ.get("WORKFLOWS_DISABLED", "").lower() in ("1", "true", "yes"):
        return False
    return bool(os.environ.get("RENDER_API_KEY"))


def _task_text(state: dict) -> str:
    messages = state.get("messages", [])
    if not messages:
        return ""
    return getattr(messages[-1], "content", "") or ""


async def _dispatch_to_workflow(spec: SubAgentSpec, task: str) -> str:
    """Run one subagent as a dedicated Render Workflow task."""
    from render_sdk import RenderAsync

    task_path = f"{WORKFLOW_NAME}/{_task_name(spec)}"
    logger.info("Dispatching subagent %s via Render Workflow %s", spec.name, task_path)

    render = RenderAsync()
    run = await render.workflows.run_task(task_path, [task])
    return _extract_output(run)


def _extract_output(run) -> str:
    """Pull the task's return value out of a completed TaskRunDetails.

    ``run_task`` returns a ``TaskRunDetails`` whose ``results`` list holds the
    task function's return value(s). We take the last result and, if a task
    happened to wrap its return in an ``{"output": ...}`` envelope, unwrap it.
    """
    value = None
    results = getattr(run, "results", None)
    if results:
        value = results[-1]
    elif hasattr(run, "output"):  # tolerate alternate SDK shapes
        value = run.output

    if isinstance(value, dict) and "output" in value:
        value = value["output"]

    if value is None:
        return ""
    return value if isinstance(value, str) else json.dumps(value)


def _task_name(spec: SubAgentSpec) -> str:
    """Map a subagent name to its Workflow task function name.

    ``research-agent`` -> ``research_agent`` (Python identifiers can't have
    hyphens, so the task functions use underscores).
    """
    return spec.name.replace("-", "_")


def workflow_subagent(spec: SubAgentSpec) -> CompiledSubAgent:
    """Build a ``CompiledSubAgent`` that dispatches ``spec`` to Render Workflows.

    Register the returned object in ``create_deep_agent(subagents=[...])``.
    """

    async def _run(state: dict) -> dict:
        task = _task_text(state)
        if workflows_enabled():
            result = await _dispatch_to_workflow(spec, task)
        else:
            logger.info("Running subagent %s in-process (Workflows disabled)", spec.name)
            result = await run_subagent_async(spec, task)
        return {"messages": [AIMessage(content=result)]}

    return CompiledSubAgent(
        name=spec.name,
        description=spec.description,
        runnable=RunnableLambda(_run),
    )
