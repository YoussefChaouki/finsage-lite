"""
FastAPI Application Entry Point

Main application factory with router registration and startup/shutdown events.
"""

import logging
from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from src.api.routers import document, health, search
from src.core.config import settings
from src.core.database import AsyncSessionLocal, init_db
from src.core.logging import setup_logging
from src.services.bm25_service import BM25Service
from src.services.embedding import EmbeddingService
from src.services.hyde_service import HyDEService

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """
    Application lifespan context manager.

    Handles:
    - Startup: Logging setup, database init, singleton service construction.
    - Shutdown: Close the HyDE httpx client.

    Singletons stored in app.state:
        embedding_service: Sentence-transformers model (loaded once).
        hyde_service: HyDE Ollama client with graceful degradation.
        bm25_service: In-memory BM25 index over all chunk content_raw.
    """
    # Startup
    setup_logging()
    await init_db()

    embedding_service = EmbeddingService()
    app.state.embedding_service = embedding_service

    hyde_service = HyDEService(embedding_service=embedding_service)
    app.state.hyde_service = hyde_service

    bm25_service = BM25Service()
    async with AsyncSessionLocal() as db:
        await bm25_service.build_index(db)
    app.state.bm25_service = bm25_service

    yield

    # Shutdown — release httpx connection pool
    await hyde_service.aclose()


app = FastAPI(
    title=settings.PROJECT_NAME,
    description="SEC 10-K filing analysis RAG system",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register routers
app.include_router(health.router, tags=["Health"])
app.include_router(document.router, tags=["Documents"])
app.include_router(search.router)


@app.get("/")
async def root() -> dict[str, str]:
    """Root endpoint."""
    return {"message": f"Welcome to {settings.PROJECT_NAME}"}
