"""FastAPI application — the trigger + human-in-the-loop layer.

Startup wiring (in order):
  1. Open one Postgres connection pool sized to the plan.
  2. Build the LangGraph Postgres checkpointer over that pool.
  3. Register the same pool for report persistence and create tables.
  4. Build the orchestrator deep agent with the checkpointer.

The orchestrator runs here (not as a Workflow task) so it can pause for human
review and resume from the Postgres checkpoint. Subagents it spawns are
dispatched to Render Workflows.
"""

from __future__ import annotations

import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from agents.orchestrator import build_orchestrator
from api.routes.runs import router as runs_router
from checkpoint.postgres import make_checkpointer, make_pool
from db.reports import init_reports, set_pool

logging.basicConfig(level=logging.INFO)


@asynccontextmanager
async def lifespan(app: FastAPI):
    pool = make_pool()
    await pool.open()
    try:
        checkpointer = await make_checkpointer(pool)
        set_pool(pool)
        await init_reports()

        app.state.pool = pool
        app.state.checkpointer = checkpointer
        app.state.orchestrator = build_orchestrator(checkpointer)
        yield
    finally:
        await pool.close()


app = FastAPI(
    title="Deep Agents on Render",
    description=(
        "A Deep Agents orchestrator with Postgres-backed checkpointing, "
        "subagents dispatched to Render Workflows, and human-in-the-loop."
    ),
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(runs_router)


@app.get("/health")
async def health():
    """Report readiness, including database connectivity."""
    pool = getattr(app.state, "pool", None)
    if pool is None:
        return JSONResponse(status_code=503, content={"status": "starting"})
    try:
        async with pool.connection() as conn:
            await conn.execute("SELECT 1")
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "unreachable"},
        )
    return {"status": "ok", "database": "ok"}
