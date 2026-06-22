"""Run and resume endpoints.

* ``POST /run/{agent}``        — start a pipeline run; returns the result or an
                                 interrupt awaiting human review.
* ``POST /resume/{thread_id}`` — supply human decisions to continue a paused run.
* ``GET  /runs/{thread_id}``   — inspect the latest report for a thread.
* ``GET  /reports``            — list recently published reports.

The orchestrator is built once at startup with the Postgres checkpointer and
stored on ``app.state``. Because state is durable, a run can be interrupted,
the process can restart, and ``/resume`` still continues from the checkpoint.
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request, status
from langchain_core.utils.uuid import uuid7
from langgraph.types import Command

from api.security import require_api_key
from db.reports import get_report_by_thread, list_reports
from models import (
    ActionRequest,
    Decision,
    ResearchReport,
    ResumeRequest,
    RunRequest,
    RunResponse,
)

logger = logging.getLogger(__name__)

router = APIRouter()

# The entry agents this API exposes. Only the orchestrator is wired up here;
# add more by mapping a name to a builder and storing them on app.state.
SUPPORTED_AGENTS = {"research"}


def _config(thread_id: str) -> dict[str, Any]:
    return {"configurable": {"thread_id": thread_id}}


def _decision_to_dict(decision: Decision) -> dict[str, Any]:
    """Convert a Decision to the LangGraph resume shape, dropping unset fields."""
    out: dict[str, Any] = {"type": decision.type}
    if decision.message is not None:
        out["message"] = decision.message
    if decision.edited_action is not None:
        out["edited_action"] = decision.edited_action
    return out


def _last_text(value: dict[str, Any]) -> str:
    for message in reversed(value.get("messages", []) if value else []):
        text = (getattr(message, "text", None) or "").strip()
        if text:
            return text
    return ""


async def _to_run_response(thread_id: str, result: Any) -> RunResponse:
    """Map a GraphOutput (version="v2") into our API response."""
    interrupts = getattr(result, "interrupts", None) or ()
    if interrupts:
        value = interrupts[0].value
        action_requests_raw = []
        review_configs = {}
        if isinstance(value, dict):
            action_requests_raw = value.get("action_requests", [])
            review_configs = {
                cfg.get("action_name"): cfg for cfg in value.get("review_configs", [])
            }
        action_requests = [
            ActionRequest(
                name=a.get("name", ""),
                args=a.get("args", {}) or {},
                allowed_decisions=review_configs.get(a.get("name"), {}).get(
                    "allowed_decisions", []
                ),
            )
            for a in action_requests_raw
        ]
        return RunResponse(
            thread_id=thread_id,
            status="interrupted",
            action_requests=action_requests,
        )

    value = getattr(result, "value", None) or {}
    report_row = await get_report_by_thread(thread_id)
    report = None
    if report_row:
        report = ResearchReport(
            title=report_row["title"],
            summary=report_row["summary"],
            body=report_row["body"],
            sources=report_row["sources"] or [],
        )
    return RunResponse(
        thread_id=thread_id,
        status="completed",
        report=report,
        result=_last_text(value),
    )


@router.post("/run/{agent}", dependencies=[Depends(require_api_key)])
async def run_agent(agent: str, request: RunRequest, http: Request) -> RunResponse:
    """Start a pipeline run for ``{agent}`` (currently: ``research``)."""
    if agent not in SUPPORTED_AGENTS:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Unknown agent '{agent}'. Supported: {sorted(SUPPORTED_AGENTS)}.",
        )

    orchestrator = http.app.state.orchestrator
    thread_id = request.thread_id or str(uuid7())
    try:
        result = await orchestrator.ainvoke(
            {"messages": [{"role": "user", "content": request.topic}]},
            config=_config(thread_id),
            version="v2",
        )
    except Exception:
        logger.exception("Run failed for thread %s", thread_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Agent run failed.",
        )
    return await _to_run_response(thread_id, result)


@router.post("/resume/{thread_id}", dependencies=[Depends(require_api_key)])
async def resume_run(thread_id: str, request: ResumeRequest, http: Request) -> RunResponse:
    """Resume a paused run with one human decision per pending action."""
    orchestrator = http.app.state.orchestrator
    decisions = [_decision_to_dict(d) for d in request.decisions]
    try:
        result = await orchestrator.ainvoke(
            Command(resume={"decisions": decisions}),
            config=_config(thread_id),
            version="v2",
        )
    except Exception:
        logger.exception("Resume failed for thread %s", thread_id)
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail="Agent resume failed.",
        )
    return await _to_run_response(thread_id, result)


@router.get("/runs/{thread_id}", dependencies=[Depends(require_api_key)])
async def get_run(thread_id: str) -> dict[str, Any]:
    """Return the most recently published report for a thread, if any."""
    report = await get_report_by_thread(thread_id)
    if not report:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No published report for this thread.",
        )
    return report


@router.get("/reports", dependencies=[Depends(require_api_key)])
async def get_reports() -> list[dict[str, Any]]:
    """List recently published reports."""
    return await list_reports()
