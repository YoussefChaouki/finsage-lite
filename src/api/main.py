"""
FastAPI Application Entry Point

Main application factory with router registration and startup/shutdown events.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request

from src.api.routers import document, health
from src.core.config import settings
from src.core.database import AsyncSessionLocal, init_db
from src.core.logging import setup_logging
from src.services.bm25_service import BM25Service

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    Handles:
    - Startup: Logging setup, database init, BM25 index construction.
    - Shutdown: Cleanup (currently none).
    """
    # Startup
    setup_logging()
    await init_db()

    bm25_service = BM25Service()
    async with AsyncSessionLocal() as db:
        await bm25_service.build_index(db)
    app.state.bm25_service = bm25_service

    yield
    # Shutdown (cleanup if needed)


def get_bm25_service(request: Request) -> BM25Service:
    """FastAPI dependency that returns the singleton BM25Service.

    Args:
        request: Current FastAPI request (injected automatically).

    Returns:
        The BM25Service instance stored in application state.
    """
    return request.app.state.bm25_service  # type: ignore[no-any-return]


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="SEC 10-K filing analysis RAG system",
    version="0.1.0",
    lifespan=lifespan,
)

# Register routers
app.include_router(health.router, tags=["Health"])
app.include_router(document.router, tags=["Documents"])


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": f"Welcome to {settings.PROJECT_NAME}"}
