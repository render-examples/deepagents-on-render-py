"""Subagent definitions — pure LangChain, no Render dependency.

Each subagent is a plain spec (name, description, system prompt, optional
tools). The *same* spec is used two ways:

1. Inside a Render Workflow task (``workflows/research/tasks.py``), where the
   subagent runs on its own dedicated instance.
2. As an in-process fallback (``dispatch/workflow_subagent.py``) when Render
   Workflows are not configured, so the example runs locally with zero infra.

Because they're ordinary ``create_agent`` graphs, they're unit-testable with
plain ``pytest`` and trivial to replace with your own.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable

from langchain.agents import create_agent
from langchain_core.messages import HumanMessage

from agents.model import get_model_id


@dataclass(frozen=True)
class SubAgentSpec:
    """A provider-agnostic subagent definition."""

    name: str
    description: str
    system_prompt: str
    tools: list[Callable] = field(default_factory=list)


RESEARCH_AGENT = SubAgentSpec(
    name="research-agent",
    description=(
        "Researches one focused subtopic and returns concise, structured "
        "findings. Delegate a single, well-scoped question at a time."
    ),
    system_prompt=(
        "You are a thorough research analyst. Given a subtopic, produce a "
        "compact findings brief:\n"
        "1. A 2-3 sentence summary.\n"
        "2. 3-6 key findings as bullet points.\n"
        "3. A short list of the most relevant sources or references you can "
        "cite from your own knowledge (name them; do not fabricate URLs).\n\n"
        "Be specific and concise. Keep the whole response under 350 words so "
        "the coordinator's context stays clean."
    ),
)

EDITOR_AGENT = SubAgentSpec(
    name="editor-agent",
    description=(
        "Synthesizes collected research findings into a single polished, "
        "well-structured report body. Give it the gathered findings."
    ),
    system_prompt=(
        "You are a sharp editor. You receive raw research findings and turn "
        "them into a cohesive report body:\n"
        "1. Open with a tight thesis paragraph.\n"
        "2. Organize the substance into 2-4 clearly titled sections.\n"
        "3. Deduplicate overlapping points and resolve contradictions.\n"
        "4. End with a short 'Bottom line' paragraph.\n\n"
        "Return clean Markdown. Do not invent facts beyond the findings."
    ),
)

ALL_SUBAGENTS: dict[str, SubAgentSpec] = {
    RESEARCH_AGENT.name: RESEARCH_AGENT,
    EDITOR_AGENT.name: EDITOR_AGENT,
}


def build_subagent(spec: SubAgentSpec):
    """Compile a subagent spec into a runnable ``create_agent`` graph."""
    return create_agent(
        model=get_model_id(),
        tools=list(spec.tools),
        system_prompt=spec.system_prompt,
        name=spec.name,
    )


def run_subagent_sync(spec: SubAgentSpec, task: str) -> str:
    """Run a subagent to completion and return its final message text.

    Used by the Render Workflow task wrappers (which are synchronous).
    """
    agent = build_subagent(spec)
    result = agent.invoke({"messages": [HumanMessage(content=task)]})
    return _final_text(result)


async def run_subagent_async(spec: SubAgentSpec, task: str) -> str:
    """Async variant used by the in-process dispatch fallback."""
    agent = build_subagent(spec)
    result = await agent.ainvoke({"messages": [HumanMessage(content=task)]})
    return _final_text(result)


def _final_text(result: dict) -> str:
    """Extract the last non-empty assistant message from an agent result."""
    for message in reversed(result.get("messages", [])):
        text = (getattr(message, "text", None) or "").strip()
        if text:
            return text
    return ""
