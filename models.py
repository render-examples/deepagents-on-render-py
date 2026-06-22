"""Shared Pydantic models — the request/response contract.

The example domain is a *research report generator*, but none of these
shapes are domain-specific in a way that matters: replace them when you
swap in your own agents.
"""

from __future__ import annotations

from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

# Upper bound on a topic/instructions string. Keeps a single request from
# pushing an unbounded prompt into the LLM (latency, memory, and cost).
MAX_TOPIC_CHARS = 8_000


class RunRequest(BaseModel):
    """Input to ``POST /run/{agent}``."""

    topic: str = Field(min_length=1, max_length=MAX_TOPIC_CHARS)
    thread_id: Optional[str] = Field(
        default=None,
        description="Optional caller-supplied thread id. One is generated if omitted.",
    )


class Decision(BaseModel):
    """One human decision for an interrupted tool call.

    Mirrors the LangGraph human-in-the-loop decision shape. ``type`` is the
    action; ``message`` (reject/respond) and ``edited_action`` (edit) are
    optional depending on the decision.
    """

    type: Literal["approve", "edit", "reject", "respond"]
    message: Optional[str] = None
    edited_action: Optional[dict[str, Any]] = None


class ResumeRequest(BaseModel):
    """Input to ``POST /resume/{thread_id}`` — one decision per pending action."""

    decisions: list[Decision] = Field(min_length=1)


class ActionRequest(BaseModel):
    """A pending tool call awaiting human review (subset of the interrupt payload)."""

    name: str
    args: dict[str, Any] = Field(default_factory=dict)
    allowed_decisions: list[str] = Field(default_factory=list)


class RunResponse(BaseModel):
    """Output of ``/run`` and ``/resume``.

    ``status`` is ``interrupted`` when the agent is paused for human review
    (inspect ``action_requests`` and call ``/resume/{thread_id}``), or
    ``completed`` when the run finished (inspect ``report`` / ``result``).
    """

    thread_id: str
    status: Literal["interrupted", "completed"]
    action_requests: list[ActionRequest] = Field(default_factory=list)
    report: Optional["ResearchReport"] = None
    result: Optional[str] = None


class ResearchReport(BaseModel):
    """The structured artifact the orchestrator publishes via ``publish_report``.

    This is the structured result of the pipeline. It is persisted to Postgres
    on approval so it survives restarts and is retrievable via ``GET /reports``.
    """

    title: str
    summary: str
    body: str
    sources: list[str] = Field(default_factory=list)
