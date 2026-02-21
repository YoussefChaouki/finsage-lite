"""
Dense Search Service

Wraps pgvector cosine-similarity retrieval with query encoding, pre-filtering,
and result mapping. Business logic lives here; raw SQL stays in the repository.
"""

from __future__ import annotations

import logging
import time

from src.core.config import settings
from src.repositories.chunk import ChunkRepository
from src.schemas.search import DenseResult, SearchFilters
from src.services.embedding import EmbeddingService

logger = logging.getLogger(__name__)


class DenseSearchService:
    """Orchestrates dense (embedding-based) retrieval for a natural language query.

    Encodes the query with the shared EmbeddingService, delegates the vector
    search to ChunkRepository, and maps raw ORM tuples to DenseResult schemas.

    Args:
        embedding_service: Shared EmbeddingService instance (model loaded once).
        chunk_repo: ChunkRepository bound to the current DB session.
    """

    def __init__(
        self,
        embedding_service: EmbeddingService,
        chunk_repo: ChunkRepository,
    ) -> None:
        self._embedding_service = embedding_service
        self._chunk_repo = chunk_repo

    async def dense_search(
        self,
        query: str,
        top_k: int | None = None,
        filters: SearchFilters | None = None,
    ) -> list[DenseResult]:
        """Perform dense retrieval for a natural language query.

        Steps:
            1. Validate query is non-empty.
            2. Encode query with EmbeddingService (single-item list).
            3. Call ChunkRepository with the query vector and filters.
            4. Map (Chunk, score) tuples to DenseResult, sorted descending.

        Args:
            query: Natural language search query. Must not be empty or whitespace.
            top_k: Number of results to return. Defaults to settings.DEFAULT_TOP_K.
            filters: Optional pre-filtering criteria (document, section, year,
                company). Defaults to no filtering.

        Returns:
            List of DenseResult objects sorted by score descending.

        Raises:
            ValueError: If query is empty or whitespace-only.
        """
        if not query.strip():
            raise ValueError("Query must not be empty or whitespace")

        resolved_top_k = top_k if top_k is not None else settings.DEFAULT_TOP_K
        resolved_filters = filters if filters is not None else SearchFilters()

        t0 = time.monotonic()

        # Encode query — embed_texts is synchronous (CPU-bound model inference)
        embeddings = self._embedding_service.embed_texts([query])
        query_vector = embeddings[0]

        # Delegate vector search + pre-filtering to the repository
        rows = await self._chunk_repo.search_by_cosine_similarity(
            embedding=query_vector,
            top_k=resolved_top_k,
            filters=resolved_filters,
        )

        elapsed_ms = (time.monotonic() - t0) * 1000
        logger.debug(
            "dense_search finished in %.1fms — %d results (top_k=%d)",
            elapsed_ms,
            len(rows),
            resolved_top_k,
        )

        results = [
            DenseResult(
                chunk_id=chunk.id,
                document_id=chunk.document_id,
                content=chunk.content_raw,
                section=chunk.section,
                section_title=chunk.section_title or "",
                score=score,
                metadata=chunk.metadata_ or {},
            )
            for chunk, score in rows
        ]

        # Repository already orders by distance, but enforce descending score here
        # to guarantee the contract regardless of future repository changes.
        results.sort(key=lambda r: r.score, reverse=True)
        return results
