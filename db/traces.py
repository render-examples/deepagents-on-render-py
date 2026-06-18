"""LangChain callback handler that writes trace data to Postgres.

Usage:
    handler = TracingCallbackHandler(agent_name="security_reviewer")
    agent.invoke(inputs, config={"callbacks": [handler]})

Every LLM call and tool call becomes a Span. The first chain_start
creates the Trace; the matching chain_end completes it.
"""

from __future__ import annotations

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from langchain_core.callbacks import BaseCallbackHandler
from langchain_core.outputs import LLMResult

from db.models import SessionLocal, Trace, Span

logger = logging.getLogger(__name__)

_PREVIEW_MAX = 500


def _truncate(text: str) -> str:
    if len(text) <= _PREVIEW_MAX:
        return text
    return text[:_PREVIEW_MAX] + "..."


def _ms_between(start: datetime, end: datetime) -> int:
    return int((end - start).total_seconds() * 1000)


class TracingCallbackHandler(BaseCallbackHandler):
    """Writes structured trace data to Postgres.

    Creates one Trace per agent run and one Span per LLM/tool call.
    Works identically in-process or inside a Render Workflow task.
    """

    def __init__(self, agent_name: str, meta: dict[str, Any] | None = None):
        self.agent_name = agent_name
        self.meta = meta

        self._trace_id: uuid.UUID | None = None
        self._root_run_id: uuid.UUID | None = None
        self._spans: dict[uuid.UUID, uuid.UUID] = {}  # langchain run_id → span id
        self._span_starts: dict[uuid.UUID, datetime] = {}

    # -- Trace lifecycle (agent start/end) --

    def on_chain_start(
        self,
        serialized: dict[str, Any],
        inputs: dict[str, Any],
        *,
        run_id: uuid.UUID,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> None:
        if self._trace_id is not None:
            return

        self._root_run_id = run_id
        try:
            with SessionLocal() as session:
                trace = Trace(
                    run_id=str(run_id),
                    agent_name=self.agent_name,
                    input_preview=_truncate(str(inputs)),
                    meta=self.meta,
                )
                session.add(trace)
                session.commit()
                self._trace_id = trace.id
        except Exception:
            logger.exception("Failed to create trace")

    def on_chain_end(
        self,
        outputs: dict[str, Any],
        *,
        run_id: uuid.UUID,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> None:
        if run_id != self._root_run_id or self._trace_id is None:
            return

        try:
            with SessionLocal() as session:
                trace = session.get(Trace, self._trace_id)
                if trace:
                    trace.status = "completed"
                    trace.output_preview = _truncate(str(outputs))
                    trace.completed_at = datetime.now(timezone.utc)
                    session.commit()
        except Exception:
            logger.exception("Failed to complete trace")

    def on_chain_error(
        self,
        error: BaseException,
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        if run_id != self._root_run_id or self._trace_id is None:
            return

        try:
            with SessionLocal() as session:
                trace = session.get(Trace, self._trace_id)
                if trace:
                    trace.status = "failed"
                    trace.output_preview = _truncate(str(error))
                    trace.completed_at = datetime.now(timezone.utc)
                    session.commit()
        except Exception:
            logger.exception("Failed to record trace error")

    # -- LLM spans --

    def on_llm_start(
        self,
        serialized: dict[str, Any],
        prompts: list[str],
        *,
        run_id: uuid.UUID,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self._record_span_start(
            run_id=run_id,
            span_type="llm",
            name=serialized.get("id", ["unknown"])[-1],
            input_data={"prompts": [_truncate(p) for p in prompts]},
        )

    def on_llm_end(
        self,
        response: LLMResult,
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        output = None
        if response.generations:
            first = response.generations[0]
            if first:
                output = {"content": _truncate(first[0].text)}
        self._record_span_end(run_id, output_data=output)

    # -- Tool spans --

    def on_tool_start(
        self,
        serialized: dict[str, Any],
        input_str: str,
        *,
        run_id: uuid.UUID,
        parent_run_id: uuid.UUID | None = None,
        **kwargs: Any,
    ) -> None:
        self._record_span_start(
            run_id=run_id,
            span_type="tool",
            name=serialized.get("name", "unknown_tool"),
            input_data={"input": _truncate(input_str)},
        )

    def on_tool_end(
        self,
        output: str,
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        self._record_span_end(
            run_id, output_data={"output": _truncate(str(output))}
        )

    def on_tool_error(
        self,
        error: BaseException,
        *,
        run_id: uuid.UUID,
        **kwargs: Any,
    ) -> None:
        self._record_span_end(
            run_id, output_data={"error": _truncate(str(error))}
        )

    # -- Internal helpers --

    def _record_span_start(
        self,
        run_id: uuid.UUID,
        span_type: str,
        name: str,
        input_data: dict | None,
    ) -> None:
        if self._trace_id is None:
            return

        now = datetime.now(timezone.utc)
        self._span_starts[run_id] = now

        try:
            with SessionLocal() as session:
                span = Span(
                    trace_id=self._trace_id,
                    span_type=span_type,
                    name=name,
                    input_data=input_data,
                    started_at=now,
                )
                session.add(span)
                session.commit()
                self._spans[run_id] = span.id
        except Exception:
            logger.exception("Failed to create span")

    def _record_span_end(
        self,
        run_id: uuid.UUID,
        output_data: dict | None,
    ) -> None:
        span_id = self._spans.get(run_id)
        if span_id is None:
            return

        now = datetime.now(timezone.utc)
        started = self._span_starts.get(run_id)
        duration = _ms_between(started, now) if started else None

        try:
            with SessionLocal() as session:
                span = session.get(Span, span_id)
                if span:
                    span.output_data = output_data
                    span.completed_at = now
                    span.duration_ms = duration
                    session.commit()
        except Exception:
            logger.exception("Failed to complete span")
