"""SQLAlchemy models for trace storage.

Every agent run produces a Trace with one or more Spans. This
works identically whether the agent runs in-process or inside
a Render Workflow task.
"""

from __future__ import annotations

import os
import uuid
from datetime import datetime, timezone

from sqlalchemy import ForeignKey, Text, create_engine
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, sessionmaker


DATABASE_URL = os.environ.get(
    "DATABASE_URL", "postgresql://localhost:5432/langchain_workflows"
)

engine = create_engine(DATABASE_URL)
SessionLocal = sessionmaker(bind=engine)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Base(DeclarativeBase):
    pass


class Trace(Base):
    """A single agent run (orchestrator, security reviewer, etc.)."""

    __tablename__ = "traces"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    run_id: Mapped[str] = mapped_column(index=True)
    agent_name: Mapped[str]
    status: Mapped[str] = mapped_column(default="running")
    input_preview: Mapped[str | None] = mapped_column(Text, default=None)
    output_preview: Mapped[str | None] = mapped_column(Text, default=None)
    started_at: Mapped[datetime] = mapped_column(default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(default=None)
    meta: Mapped[dict | None] = mapped_column(JSONB, default=None)


class Span(Base):
    """A single step within a trace: an LLM call, tool call, or chain."""

    __tablename__ = "spans"

    id: Mapped[uuid.UUID] = mapped_column(primary_key=True, default=uuid.uuid4)
    trace_id: Mapped[uuid.UUID] = mapped_column(ForeignKey("traces.id"), index=True)
    parent_span_id: Mapped[uuid.UUID | None] = mapped_column(default=None)
    span_type: Mapped[str]  # "llm", "tool"
    name: Mapped[str]
    input_data: Mapped[dict | None] = mapped_column(JSONB, default=None)
    output_data: Mapped[dict | None] = mapped_column(JSONB, default=None)
    started_at: Mapped[datetime] = mapped_column(default=_utcnow)
    completed_at: Mapped[datetime | None] = mapped_column(default=None)
    duration_ms: Mapped[int | None] = mapped_column(default=None)
    meta: Mapped[dict | None] = mapped_column(JSONB, default=None)


def init_db():
    """Create all tables. Call once at startup."""
    Base.metadata.create_all(engine)
