"""Persistence for published reports — the tangible pipeline artifact.

Reuses the same ``AsyncConnectionPool`` as the checkpointer so the app stays
within one connection budget. The pool is registered once at startup via
``set_pool`` and consumed by the ``publish_report`` tool and ``GET /reports``.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from psycopg_pool import AsyncConnectionPool

_pool: Optional[AsyncConnectionPool] = None

_CREATE_TABLE = """
CREATE TABLE IF NOT EXISTS reports (
    id          BIGSERIAL PRIMARY KEY,
    thread_id   TEXT NOT NULL,
    title       TEXT NOT NULL,
    summary     TEXT NOT NULL,
    body        TEXT NOT NULL,
    sources     JSONB NOT NULL DEFAULT '[]'::jsonb,
    created_at  TIMESTAMPTZ NOT NULL DEFAULT now()
)
"""

_CREATE_INDEX = """
CREATE INDEX IF NOT EXISTS reports_thread_id_idx ON reports (thread_id)
"""


def set_pool(pool: AsyncConnectionPool) -> None:
    """Register the shared pool. Call once during startup."""
    global _pool
    _pool = pool


def _require_pool() -> AsyncConnectionPool:
    if _pool is None:
        raise RuntimeError("Report store pool is not initialized. Call set_pool() first.")
    return _pool


async def init_reports() -> None:
    """Create the reports table and index if they do not exist."""
    async with _require_pool().connection() as conn:
        await conn.execute(_CREATE_TABLE)
        await conn.execute(_CREATE_INDEX)


async def insert_report(
    thread_id: str,
    title: str,
    summary: str,
    body: str,
    sources: list[str],
) -> dict[str, Any]:
    """Persist a published report and return the stored row."""
    async with _require_pool().connection() as conn:
        cur = await conn.execute(
            """
            INSERT INTO reports (thread_id, title, summary, body, sources)
            VALUES (%s, %s, %s, %s, %s)
            RETURNING id, thread_id, title, summary, body, sources, created_at
            """,
            (thread_id, title, summary, body, json.dumps(sources)),
        )
        return await cur.fetchone()


async def get_report_by_thread(thread_id: str) -> Optional[dict[str, Any]]:
    """Return the most recent report for a thread, if any."""
    async with _require_pool().connection() as conn:
        cur = await conn.execute(
            """
            SELECT id, thread_id, title, summary, body, sources, created_at
            FROM reports
            WHERE thread_id = %s
            ORDER BY created_at DESC
            LIMIT 1
            """,
            (thread_id,),
        )
        return await cur.fetchone()


async def list_reports(limit: int = 50) -> list[dict[str, Any]]:
    """Return recent reports for the dashboard / API."""
    async with _require_pool().connection() as conn:
        cur = await conn.execute(
            """
            SELECT id, thread_id, title, summary, body, sources, created_at
            FROM reports
            ORDER BY created_at DESC
            LIMIT %s
            """,
            (limit,),
        )
        return await cur.fetchall()
