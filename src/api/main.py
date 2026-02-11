"""
FastAPI Application Entry Point

Main application factory with router registration and startup/shutdown events.
"""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from src.api.routers import health
from src.core.config import settings
from src.core.database import init_db
from src.core.logging import setup_logging


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    Handles:
    - Startup: Logging setup, database initialization
    - Shutdown: Cleanup (currently none)
    """
    # Startup
    setup_logging()
    await init_db()
    yield
    # Shutdown (cleanup if needed)


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="SEC 10-K filing analysis RAG system",
    version="0.1.0",
    lifespan=lifespan,
)

# Register routers
app.include_router(health.router, tags=["Health"])


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": f"Welcome to {settings.PROJECT_NAME}"}
