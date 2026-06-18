"""FastAPI application — thin trigger layer for the review pipeline."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse
from sqlalchemy import text

from api.routes.reviews import router as reviews_router
from api.ui import create_ui_router
from db.models import engine, init_db


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    yield


app = FastAPI(
    title="Code Review Pipeline",
    description="Multi-agent code review powered by LangChain and Render Workflows.",
    version="0.1.0",
    lifespan=lifespan,
)

app.include_router(reviews_router)
app.include_router(create_ui_router())


@app.get("/health")
async def health():
    """Report readiness, including database connectivity."""
    try:
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
    except Exception:
        return JSONResponse(
            status_code=503,
            content={"status": "unhealthy", "database": "unreachable"},
        )
    return {"status": "ok", "database": "ok"}
