"""FastAPI application — thin trigger layer for the review pipeline."""

from contextlib import asynccontextmanager

from fastapi import FastAPI

from api.routes.reviews import router as reviews_router
from api.ui import create_ui_router
from db.models import init_db


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
    return {"status": "ok"}
