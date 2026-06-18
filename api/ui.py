"""Mountable UI router — serves the trace explorer dashboard."""

from __future__ import annotations

import html
from pathlib import Path
from uuid import UUID

from fastapi import APIRouter
from fastapi.responses import HTMLResponse, Response
from sqlalchemy import select

from db.models import SessionLocal, Trace, Span

TEMPLATES_DIR = Path(__file__).parent / "templates"
STATIC_DIR = Path(__file__).parent / "static"


def _esc(value: str) -> str:
    return html.escape(value, quote=True)


def create_ui_router(title: str = "Code Review Pipeline") -> APIRouter:
    router = APIRouter()

    @router.get("/", response_class=HTMLResponse)
    async def dashboard():
        template = (TEMPLATES_DIR / "dashboard.html").read_text()
        return HTMLResponse(template.replace("{{TITLE}}", _esc(title)))

    @router.get("/dashboard.css")
    async def css():
        content = (STATIC_DIR / "styles.css").read_text()
        return Response(content=content, media_type="text/css; charset=utf-8")

    @router.get("/api/traces")
    async def list_traces():
        with SessionLocal() as session:
            stmt = select(Trace).order_by(Trace.started_at.desc()).limit(50)
            traces = session.scalars(stmt).all()
            return [_trace_dict(t) for t in traces]

    @router.get("/api/traces/{trace_id}/spans")
    async def get_spans(trace_id: UUID):
        with SessionLocal() as session:
            stmt = (
                select(Span)
                .where(Span.trace_id == trace_id)
                .order_by(Span.started_at)
            )
            spans = session.scalars(stmt).all()
            return [_span_dict(s) for s in spans]

    return router


def _trace_dict(t: Trace) -> dict:
    return {
        "id": str(t.id),
        "run_id": t.run_id,
        "agent_name": t.agent_name,
        "status": t.status,
        "input_preview": t.input_preview,
        "output_preview": t.output_preview,
        "started_at": t.started_at.isoformat() if t.started_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
    }


def _span_dict(s: Span) -> dict:
    return {
        "id": str(s.id),
        "trace_id": str(s.trace_id),
        "span_type": s.span_type,
        "name": s.name,
        "input_data": s.input_data,
        "output_data": s.output_data,
        "started_at": s.started_at.isoformat() if s.started_at else None,
        "completed_at": s.completed_at.isoformat() if s.completed_at else None,
        "duration_ms": s.duration_ms,
    }
