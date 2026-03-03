"""
Search Router

Unified search endpoint orchestrating dense, sparse, and hybrid retrieval
with optional HyDE query expansion. Latency is logged per-request via the
underlying RetrievalService.

Routes:
    POST /api/v1/search              — execute search (dense / sparse / hybrid)
    GET  /api/v1/search/health       — BM25 index status and HyDE availability
    POST /api/v1/search/rebuild-index — rebuild the in-memory BM25 index
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, Request
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.database import get_db
from src.repositories.chunk import ChunkRepository
from src.schemas.search import SearchHealthResponse, SearchRequest, SearchResponse
from src.services.bm25_service import BM25Service
from src.services.embedding import EmbeddingService
from src.services.hyde_service import HyDEService
from src.services.retrieval_service import RetrievalService
from src.services.search import DenseSearchService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/search", tags=["Search"])


# ---------------------------------------------------------------------------
# Dependency providers (public so tests can override them)
# ---------------------------------------------------------------------------


def get_bm25_service(request: Request) -> BM25Service:
    """Return the singleton BM25Service from application state.

    Args:
        request: Current FastAPI request (injected automatically).

    Returns:
        The BM25Service instance initialized at startup.
    """
    return request.app.state.bm25_service  # type: ignore[no-any-return]


def get_embedding_service(request: Request) -> EmbeddingService:
    """Return the singleton EmbeddingService from application state.

    Args:
        request: Current FastAPI request (injected automatically).

    Returns:
        The EmbeddingService instance initialized at startup.
    """
    return request.app.state.embedding_service  # type: ignore[no-any-return]


def get_hyde_service(request: Request) -> HyDEService:
    """Return the singleton HyDEService from application state.

    Args:
        request: Current FastAPI request (injected automatically).

    Returns:
        The HyDEService instance initialized at startup.
    """
    return request.app.state.hyde_service  # type: ignore[no-any-return]


def get_retrieval_service(
    db: AsyncSession = Depends(get_db),
    bm25_service: BM25Service = Depends(get_bm25_service),
    embedding_service: EmbeddingService = Depends(get_embedding_service),
    hyde_service: HyDEService = Depends(get_hyde_service),
) -> RetrievalService:
    """Build a per-request RetrievalService with all dependencies wired.

    Assembles DenseSearchService (per-request, DB-scoped) using the shared
    EmbeddingService singleton and a ChunkRepository bound to the current
    session, then composes it with the singleton BM25Service and HyDEService.

    Args:
        db: Per-request async DB session.
        bm25_service: Singleton in-memory BM25 index.
        embedding_service: Shared sentence-transformers model.
        hyde_service: HyDE expansion service (Ollama-backed with fallback).

    Returns:
        A fully wired RetrievalService ready to execute retrieval.
    """
    chunk_repo = ChunkRepository(db)
    dense_service = DenseSearchService(
        embedding_service=embedding_service,
        chunk_repo=chunk_repo,
    )
    return RetrievalService(
        dense_search_service=dense_service,
        bm25_service=bm25_service,
        hyde_service=hyde_service,
    )


# ---------------------------------------------------------------------------
# Endpoints
# ---------------------------------------------------------------------------


@router.post("", response_model=SearchResponse)
async def search(
    body: SearchRequest,
    retrieval_service: RetrievalService = Depends(get_retrieval_service),
) -> SearchResponse:
    """Execute search across SEC 10-K chunk embeddings.

    Dispatches to dense, sparse, or hybrid retrieval based on
    ``body.search_mode``. When ``body.use_hyde=True`` and the query is
    analytical, HyDE expansion replaces the raw query embedding for dense
    retrieval (BM25 always uses the original query text).

    Latency for each sub-step (BM25, dense, RRF, HyDE) is logged at DEBUG
    level by the underlying services; overall request latency is reported
    in the response body.

    Args:
        body: Validated search request.
        retrieval_service: Wired retrieval orchestrator (injected).

    Returns:
        SearchResponse with ranked results, diagnostic metadata, and latency.
    """
    logger.info(
        "search request — mode=%s top_k=%d use_hyde=%s query=%r",
        body.search_mode,
        body.top_k,
        body.use_hyde,
        body.query[:80],
    )
    response = await retrieval_service.search(body)
    logger.info(
        "search complete — %d results in %.1fms (hyde_used=%s)",
        response.total,
        response.latency_ms,
        response.hyde_used,
    )
    return response


@router.get("/health", response_model=SearchHealthResponse)
async def search_health(
    bm25_service: BM25Service = Depends(get_bm25_service),
    hyde_service: HyDEService = Depends(get_hyde_service),
) -> SearchHealthResponse:
    """Report BM25 index status and HyDE (Ollama) availability.

    Performs a lightweight reachability probe against the configured Ollama
    endpoint to determine whether HyDE expansion is available at query time.

    Args:
        bm25_service: Singleton BM25 index accessed via app state.
        hyde_service: HyDE service used to probe Ollama reachability.

    Returns:
        SearchHealthResponse with index size, build status, HyDE flag, and
        the configured Ollama model name.
    """
    stats = bm25_service.get_stats()
    hyde_available = await hyde_service.is_available()
    return SearchHealthResponse(
        bm25_index_size=stats["chunk_count"],
        bm25_is_built=stats["is_built"],
        hyde_available=hyde_available,
        ollama_model=settings.OLLAMA_MODEL,
    )


@router.post("/rebuild-index")
async def rebuild_index(
    db: AsyncSession = Depends(get_db),
    bm25_service: BM25Service = Depends(get_bm25_service),
) -> dict[str, int]:
    """Rebuild the in-memory BM25 index from the current database contents.

    Must be called after new documents are ingested to make them searchable
    via sparse retrieval without restarting the server.

    Args:
        db: Async DB session for loading chunk data.
        bm25_service: Singleton BM25 index to rebuild in place.

    Returns:
        Dictionary with ``chunk_count`` reporting the number of newly indexed
        chunks.
    """
    logger.info("BM25 index rebuild triggered via API")
    await bm25_service.build_index(db)
    stats = bm25_service.get_stats()
    logger.info("BM25 index rebuild complete: %d chunks indexed", stats["chunk_count"])
    return {"chunk_count": stats["chunk_count"]}
