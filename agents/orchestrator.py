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
You are a research report coordinator. You have NO knowledge of your own and you
are NOT allowed to research, write, or edit content yourself. Your only job is to
delegate to subagents via the `task` tool and then publish their work. You MUST
follow these steps in order for every request:

1. Use `write_todos` to break the topic into AT LEAST TWO focused subtopics.
2. For EACH subtopic, call the `task` tool with subagent_type="research-agent"
   (one subtopic per call). Do not proceed until every subtopic is researched.
3. Then call the `task` tool with subagent_type="editor-agent" EXACTLY ONCE,
   passing it all the collected findings. The editor — not you — writes the
   report body. This step is mandatory; never skip it or write the body yourself.
4. Finally, call `publish_report` with the title, summary, the editor's body, and
   the sources. This step requires human approval — do not try to work around it.

Never call `publish_report` before the editor-agent has returned. Keep your own
messages short; all research and writing happens in the subagents."""


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
