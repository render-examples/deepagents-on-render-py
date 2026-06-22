"""The orchestrator — a Deep Agent that coordinates the pipeline.

It is itself a deep agent. Its subagents are registered as
``CompiledSubAgent``s that dispatch to Render Workflows (see
``dispatch/workflow_subagent.py``), so when the agent calls the built-in
``task`` tool, each subagent runs on its own Workflow instance instead of
in-process.

State is persisted by the Postgres checkpointer passed in at build time, and
``publish_report`` is gated behind a human-in-the-loop interrupt.
"""

from __future__ import annotations

from deepagents import create_deep_agent
from langgraph.checkpoint.base import BaseCheckpointSaver

from agents.model import get_model_id
from agents.subagents import EDITOR_AGENT, RESEARCH_AGENT
from agents.tools import publish_report
from dispatch.workflow_subagent import workflow_subagent

SYSTEM_PROMPT = """\
You are a research report coordinator. You have no research knowledge of your
own — you must delegate. Given a topic, you:

1. Use `write_todos` to plan the report (what subtopics to research).
2. For each subtopic, call the `task` tool with subagent_type="research-agent"
   to gather findings. Delegate one focused subtopic at a time; you may issue
   several research tasks.
3. Once you have findings, call the `task` tool with subagent_type="editor-agent",
   passing it all the collected findings, to produce a polished report body.
4. Finally, call `publish_report` with the finished title, summary, body, and
   sources. This step requires human approval — do not try to work around it.

Keep your own messages short; the heavy lifting belongs in the subagents."""


def build_orchestrator(checkpointer: BaseCheckpointSaver):
    """Compile the orchestrator deep agent.

    Args:
        checkpointer: A LangGraph checkpointer (Postgres in production). Required
            for human-in-the-loop: it persists the interrupted state so a run
            can pause, the process can restart, and ``/resume`` can continue.
    """
    return create_deep_agent(
        model=get_model_id(),
        system_prompt=SYSTEM_PROMPT,
        tools=[publish_report],
        subagents=[
            workflow_subagent(RESEARCH_AGENT),
            workflow_subagent(EDITOR_AGENT),
        ],
        interrupt_on={"publish_report": True},
        checkpointer=checkpointer,
    )
