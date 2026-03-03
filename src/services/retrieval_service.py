"""
Retrieval Service

Orchestrates dense, sparse, and hybrid (BM25 + dense + RRF) retrieval.
All search modes are accessible through a single ``search()`` entry point.
"""

from __future__ import annotations

import logging
import time
import uuid

from src.core.config import settings
from src.schemas.search import (
    DenseResult,
    SearchFilters,
    SearchRequest,
    SearchResponse,
    SearchResult,
    SparseResult,
)
from src.services.bm25_service import BM25Service
from src.services.hyde_service import HyDEService, is_analytical_query
from src.services.search import DenseSearchService

logger = logging.getLogger(__name__)


# ---------------------------------------------------------------------------
# RRF fusion — module-level utility
# ---------------------------------------------------------------------------


def reciprocal_rank_fusion(
    dense_results: list[DenseResult],
    sparse_results: list[SparseResult],
    k: int | None = None,
) -> list[SearchResult]:
    """Fuse dense and sparse ranked lists using Reciprocal Rank Fusion (RRF).

    For each chunk present in either list the RRF contribution is::

        score[chunk_id] += 1 / (k + rank)

    where ``rank`` is 1-based (best = 1). Scores are then normalised to [0, 1]
    by dividing by the maximum score. Individual dense and sparse scores are
    preserved in the output for debugging and comparison.

    Args:
        dense_results: Ranked list from dense (embedding) retrieval.
        sparse_results: Ranked list from BM25 sparse retrieval.
        k: RRF smoothing constant. Defaults to ``settings.RRF_K`` (60).

    Returns:
        List of :class:`~src.schemas.search.SearchResult` objects sorted by
        RRF score descending. Empty if both input lists are empty.
    """
    rrf_k = k if k is not None else settings.RRF_K

    # Accumulate raw RRF scores per chunk_id
    rrf_scores: dict[uuid.UUID, float] = {}
    dense_scores: dict[uuid.UUID, float] = {}
    sparse_scores: dict[uuid.UUID, float] = {}

    for rank, d_result in enumerate(dense_results, start=1):
        cid = d_result.chunk_id
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (rrf_k + rank)
        dense_scores[cid] = d_result.score

    for rank, s_result in enumerate(sparse_results, start=1):
        cid = s_result.chunk_id
        rrf_scores[cid] = rrf_scores.get(cid, 0.0) + 1.0 / (rrf_k + rank)
        sparse_scores[cid] = s_result.bm25_score

    if not rrf_scores:
        return []

    max_score = max(rrf_scores.values())

    # Build a lookup: chunk_id → source result (prefer dense for metadata)
    chunk_data: dict[uuid.UUID, DenseResult | SparseResult] = {}
    for sr in sparse_results:
        chunk_data[sr.chunk_id] = sr
    for dr in dense_results:
        chunk_data[dr.chunk_id] = dr  # dense wins if both present

    fused: list[SearchResult] = []
    for cid, raw_score in rrf_scores.items():
        normalised = raw_score / max_score if max_score > 0.0 else 0.0
        src = chunk_data[cid]
        fused.append(
            SearchResult(
                chunk_id=cid,
                document_id=src.document_id,
                content=src.content,
                section=src.section,
                section_title=src.section_title,
                score=normalised,
                dense_score=dense_scores.get(cid),
                sparse_score=sparse_scores.get(cid),
                metadata=src.metadata,
            )
        )

    fused.sort(key=lambda r: r.score, reverse=True)
    return fused


# ---------------------------------------------------------------------------
# RetrievalService
# ---------------------------------------------------------------------------


class RetrievalService:
    """Orchestrates dense, sparse, and hybrid retrieval with optional HyDE.

    Intended to be instantiated per-request (or held as a scoped dependency)
    with a shared BM25Service singleton and HyDEService singleton.

    Args:
        dense_search_service: DenseSearchService instance for vector search.
        bm25_service: BM25Service singleton with pre-built index.
        hyde_service: HyDEService for optional query expansion.
    """

    def __init__(
        self,
        dense_search_service: DenseSearchService,
        bm25_service: BM25Service,
        hyde_service: HyDEService,
    ) -> None:
        self._dense = dense_search_service
        self._bm25 = bm25_service
        self._hyde = hyde_service

    async def search(self, request: SearchRequest) -> SearchResponse:
        """Execute retrieval according to the request parameters.

        Steps:
            1. Start latency timer.
            2. If ``use_hyde`` and mode is not ``"sparse"``, attempt HyDE
               embedding expansion (falls back silently on failure).
            3. Dispatch to the appropriate retrieval path:
               - ``"dense"``  → dense_search only.
               - ``"sparse"`` → BM25 search only.
               - ``"hybrid"`` → both, then RRF fusion.
            4. Cap results at ``request.top_k``.
            5. Return a :class:`~src.schemas.search.SearchResponse` with
               latency measurement and metadata.

        Args:
            request: Validated SearchRequest from the API layer.

        Returns:
            SearchResponse containing ranked results and diagnostic metadata.
        """
        t0 = time.perf_counter()

        mode = request.search_mode
        filters = request.filters
        top_k = request.top_k
        query = request.query

        # ------------------------------------------------------------------
        # HyDE expansion decision
        # ------------------------------------------------------------------
        # HyDE is applied only when:
        #   (a) caller opts in via use_hyde=True
        #   (b) the query is analytical (heuristic)
        #   (c) we need dense embeddings (mode != "sparse")
        hyde_applied = request.use_hyde and mode != "sparse" and is_analytical_query(query)

        query_embedding: list[float] | None = None
        if hyde_applied:
            query_embedding = await self._hyde.expand_query_to_embedding(query)
            logger.debug("HyDE embedding computed for query: %r", query[:80])

        # ------------------------------------------------------------------
        # Retrieval dispatch
        # ------------------------------------------------------------------
        results: list[SearchResult]

        if mode == "dense":
            dense = await self._run_dense(query, query_embedding, top_k, filters)
            results = [_dense_to_search_result(r) for r in dense]

        elif mode == "sparse":
            sparse = await self._bm25.search(query=query, top_k=top_k, filters=filters)
            results = [_sparse_to_search_result(r) for r in sparse]

        else:  # hybrid
            dense, sparse = await self._run_both(query, query_embedding, top_k, filters)
            results = reciprocal_rank_fusion(dense, sparse)[:top_k]

        latency_ms = (time.perf_counter() - t0) * 1000
        logger.debug(
            "search finished in %.1fms — mode=%s top_k=%d results=%d",
            latency_ms,
            mode,
            top_k,
            len(results),
        )

        return SearchResponse(
            results=results[:top_k],
            total=len(results[:top_k]),
            query=query,
            search_mode=mode,
            hyde_used=hyde_applied,
            latency_ms=latency_ms,
        )

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    async def _run_dense(
        self,
        query: str,
        query_embedding: list[float] | None,
        top_k: int,
        filters: SearchFilters,
    ) -> list[DenseResult]:
        """Run dense search, optionally injecting a pre-computed embedding."""
        if query_embedding is not None:
            return await self._dense.dense_search_with_embedding(
                query_embedding=query_embedding,
                top_k=top_k,
                filters=filters,
            )
        return await self._dense.dense_search(query=query, top_k=top_k, filters=filters)

    async def _run_both(
        self,
        query: str,
        query_embedding: list[float] | None,
        top_k: int,
        filters: SearchFilters,
    ) -> tuple[list[DenseResult], list[SparseResult]]:
        """Run dense and sparse searches and return both candidate lists.

        Uses a larger intermediate candidate pool (at least 20) for better
        RRF coverage before the final top_k slice is applied.
        """
        candidate_k = max(20, top_k)
        dense = await self._run_dense(query, query_embedding, candidate_k, filters)
        sparse = await self._bm25.search(query=query, top_k=candidate_k, filters=filters)
        return dense, sparse


# ---------------------------------------------------------------------------
# Result adapters
# ---------------------------------------------------------------------------


def _dense_to_search_result(r: DenseResult) -> SearchResult:
    """Convert a DenseResult to a SearchResult (score unchanged, no sparse)."""
    return SearchResult(
        chunk_id=r.chunk_id,
        document_id=r.document_id,
        content=r.content,
        section=r.section,
        section_title=r.section_title,
        score=r.score,
        dense_score=r.score,
        sparse_score=None,
        metadata=r.metadata,
    )


def _sparse_to_search_result(r: SparseResult) -> SearchResult:
    """Convert a SparseResult to a SearchResult (score = bm25_score, no dense)."""
    return SearchResult(
        chunk_id=r.chunk_id,
        document_id=r.document_id,
        content=r.content,
        section=r.section,
        section_title=r.section_title,
        score=r.bm25_score,
        dense_score=None,
        sparse_score=r.bm25_score,
        metadata=r.metadata,
    )
