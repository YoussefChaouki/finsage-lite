"""
Unit Tests — RetrievalService

All dependencies (DenseSearchService, BM25Service, HyDEService) are mocked
so these tests run without a database or Ollama server.
"""

from __future__ import annotations

import uuid
from unittest.mock import AsyncMock, MagicMock

import pytest

from src.models.chunk import SectionType
from src.schemas.search import (
    DenseResult,
    SearchFilters,
    SearchRequest,
    SparseResult,
)
from src.services.retrieval_service import RetrievalService

# ---------------------------------------------------------------------------
# Shared constants / helpers
# ---------------------------------------------------------------------------

_SECTION = SectionType.ITEM_1A
_DOC_ID = uuid.uuid4()


def _dense_result(chunk_id: uuid.UUID, score: float = 0.9) -> DenseResult:
    return DenseResult(
        chunk_id=chunk_id,
        document_id=_DOC_ID,
        content="dense text",
        section=_SECTION,
        section_title="Risk Factors",
        score=score,
        metadata={},
    )


def _sparse_result(chunk_id: uuid.UUID, bm25_score: float = 5.0, rank: int = 1) -> SparseResult:
    return SparseResult(
        chunk_id=chunk_id,
        document_id=_DOC_ID,
        content="sparse text",
        section=_SECTION,
        section_title="Risk Factors",
        bm25_score=bm25_score,
        rank=rank,
        metadata={},
    )


def _make_service(
    dense_results: list[DenseResult] | None = None,
    sparse_results: list[SparseResult] | None = None,
    hyde_embedding: list[float] | None = None,
    hyde_is_analytical: bool = False,
) -> tuple[RetrievalService, MagicMock, MagicMock, MagicMock]:
    """Return (service, dense_mock, bm25_mock, hyde_mock)."""
    dense_mock = MagicMock()
    dense_mock.dense_search = AsyncMock(return_value=dense_results or [])
    dense_mock.dense_search_with_embedding = AsyncMock(return_value=dense_results or [])

    bm25_mock = MagicMock()
    bm25_mock.search = AsyncMock(return_value=sparse_results or [])

    hyde_mock = MagicMock()
    hyde_mock.expand_query_to_embedding = AsyncMock(return_value=hyde_embedding or [0.1] * 384)

    svc = RetrievalService(
        dense_search_service=dense_mock,
        bm25_service=bm25_mock,
        hyde_service=hyde_mock,
    )
    return svc, dense_mock, bm25_mock, hyde_mock


# ---------------------------------------------------------------------------
# Mode "dense" — only DenseSearchService called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_dense_mode_calls_only_dense() -> None:
    """In dense mode BM25 must not be invoked."""
    cid = uuid.uuid4()
    svc, dense_mock, bm25_mock, _ = _make_service(dense_results=[_dense_result(cid)])

    request = SearchRequest(query="Apple revenue", search_mode="dense")
    response = await svc.search(request)

    dense_mock.dense_search.assert_called_once()
    bm25_mock.search.assert_not_called()
    assert len(response.results) == 1
    assert response.results[0].chunk_id == cid


@pytest.mark.asyncio
async def test_dense_mode_response_fields() -> None:
    """Dense mode response must echo mode and have hyde_used=False."""
    svc, _, _, _ = _make_service()
    request = SearchRequest(query="total revenue", search_mode="dense", use_hyde=False)
    response = await svc.search(request)

    assert response.search_mode == "dense"
    assert response.query == "total revenue"
    assert response.hyde_used is False


@pytest.mark.asyncio
async def test_dense_mode_preserves_dense_score() -> None:
    """Dense-mode SearchResult must carry dense_score and no sparse_score."""
    cid = uuid.uuid4()
    svc, _, _, _ = _make_service(dense_results=[_dense_result(cid, score=0.75)])

    response = await svc.search(SearchRequest(query="revenue", search_mode="dense"))
    r = response.results[0]

    assert r.dense_score == pytest.approx(0.75)
    assert r.sparse_score is None


# ---------------------------------------------------------------------------
# Mode "sparse" — only BM25Service called
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_sparse_mode_calls_only_bm25() -> None:
    """In sparse mode DenseSearchService must not be invoked."""
    cid = uuid.uuid4()
    svc, dense_mock, bm25_mock, _ = _make_service(sparse_results=[_sparse_result(cid)])

    request = SearchRequest(query="Apple revenue", search_mode="sparse")
    response = await svc.search(request)

    bm25_mock.search.assert_called_once()
    dense_mock.dense_search.assert_not_called()
    dense_mock.dense_search_with_embedding.assert_not_called()
    assert len(response.results) == 1
    assert response.results[0].chunk_id == cid


@pytest.mark.asyncio
async def test_sparse_mode_hyde_never_applied() -> None:
    """HyDE must not run in sparse mode even if use_hyde=True."""
    svc, _, _, hyde_mock = _make_service()
    request = SearchRequest(query="compare revenue trends", search_mode="sparse", use_hyde=True)
    response = await svc.search(request)

    hyde_mock.expand_query_to_embedding.assert_not_called()
    assert response.hyde_used is False


@pytest.mark.asyncio
async def test_sparse_mode_preserves_bm25_score() -> None:
    """Sparse-mode SearchResult must carry sparse_score and no dense_score."""
    cid = uuid.uuid4()
    svc, _, _, _ = _make_service(sparse_results=[_sparse_result(cid, bm25_score=7.3)])

    response = await svc.search(SearchRequest(query="revenue", search_mode="sparse"))
    r = response.results[0]

    assert r.sparse_score == pytest.approx(7.3)
    assert r.dense_score is None


# ---------------------------------------------------------------------------
# Mode "hybrid" — both called, RRF applied
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hybrid_calls_both_services() -> None:
    """Hybrid mode must invoke both dense and BM25 retrieval."""
    d_id, s_id = uuid.uuid4(), uuid.uuid4()
    svc, dense_mock, bm25_mock, _ = _make_service(
        dense_results=[_dense_result(d_id)],
        sparse_results=[_sparse_result(s_id)],
    )

    await svc.search(SearchRequest(query="revenue", search_mode="hybrid"))

    dense_mock.dense_search.assert_called_once()
    bm25_mock.search.assert_called_once()


@pytest.mark.asyncio
async def test_hybrid_deduplicates_shared_chunk() -> None:
    """A chunk returned by both dense and sparse must appear only once."""
    shared = uuid.uuid4()
    svc, _, _, _ = _make_service(
        dense_results=[_dense_result(shared)],
        sparse_results=[_sparse_result(shared)],
    )

    response = await svc.search(SearchRequest(query="revenue", search_mode="hybrid"))
    chunk_ids = [r.chunk_id for r in response.results]
    assert chunk_ids.count(shared) == 1


@pytest.mark.asyncio
async def test_hybrid_shared_chunk_scores_higher_than_exclusive() -> None:
    """RRF must give a higher score to a chunk that appears in both lists."""
    shared = uuid.uuid4()
    exclusive_dense = uuid.uuid4()

    svc, _, _, _ = _make_service(
        dense_results=[_dense_result(shared), _dense_result(exclusive_dense)],
        sparse_results=[_sparse_result(shared)],
    )

    response = await svc.search(SearchRequest(query="revenue", search_mode="hybrid"))
    result_map = {r.chunk_id: r for r in response.results}

    assert result_map[shared].score > result_map[exclusive_dense].score


@pytest.mark.asyncio
async def test_hybrid_results_sorted_descending() -> None:
    """Hybrid results must be sorted by RRF score descending."""
    ids = [uuid.uuid4() for _ in range(3)]
    svc, _, _, _ = _make_service(
        dense_results=[_dense_result(ids[i], score=0.9 - i * 0.1) for i in range(3)],
        sparse_results=[_sparse_result(ids[i], rank=i + 1) for i in range(3)],
    )

    response = await svc.search(SearchRequest(query="revenue", search_mode="hybrid"))
    scores = [r.score for r in response.results]
    assert scores == sorted(scores, reverse=True)


# ---------------------------------------------------------------------------
# Score normalisation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hybrid_scores_normalised_to_0_1() -> None:
    """All hybrid RRF scores must lie in [0, 1]."""
    ids = [uuid.uuid4() for _ in range(4)]
    svc, _, _, _ = _make_service(
        dense_results=[_dense_result(ids[0]), _dense_result(ids[1])],
        sparse_results=[_sparse_result(ids[2]), _sparse_result(ids[0])],
    )

    response = await svc.search(SearchRequest(query="revenue", search_mode="hybrid"))
    for r in response.results:
        assert 0.0 <= r.score <= 1.0


# ---------------------------------------------------------------------------
# Latency measurement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_latency_ms_is_positive() -> None:
    """latency_ms in SearchResponse must be a positive float."""
    svc, _, _, _ = _make_service()
    response = await svc.search(SearchRequest(query="revenue"))
    assert response.latency_ms > 0.0


# ---------------------------------------------------------------------------
# top_k enforcement
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_top_k_limits_results() -> None:
    """Returned results must not exceed request.top_k."""
    ids = [uuid.uuid4() for _ in range(10)]
    svc, _, _, _ = _make_service(
        dense_results=[_dense_result(i) for i in ids],
        sparse_results=[_sparse_result(i, rank=r + 1) for r, i in enumerate(ids)],
    )

    response = await svc.search(SearchRequest(query="revenue", search_mode="hybrid", top_k=3))
    assert len(response.results) <= 3
    assert response.total <= 3


# ---------------------------------------------------------------------------
# HyDE integration
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_hyde_applied_for_analytical_dense_query() -> None:
    """HyDE must be applied when use_hyde=True and query is analytical."""
    svc, dense_mock, _, hyde_mock = _make_service()

    # "compare" is in ANALYTICAL_KEYWORDS
    request = SearchRequest(
        query="compare revenue trends across segments", search_mode="dense", use_hyde=True
    )
    response = await svc.search(request)

    hyde_mock.expand_query_to_embedding.assert_called_once()
    dense_mock.dense_search_with_embedding.assert_called_once()
    dense_mock.dense_search.assert_not_called()
    assert response.hyde_used is True


@pytest.mark.asyncio
async def test_hyde_skipped_for_factual_query() -> None:
    """HyDE must be skipped when query is factual (no analytical keywords)."""
    svc, dense_mock, _, hyde_mock = _make_service()

    request = SearchRequest(
        query="What is Apple's total revenue?", search_mode="dense", use_hyde=True
    )
    response = await svc.search(request)

    hyde_mock.expand_query_to_embedding.assert_not_called()
    dense_mock.dense_search.assert_called_once()
    assert response.hyde_used is False


@pytest.mark.asyncio
async def test_hyde_not_applied_when_use_hyde_false() -> None:
    """HyDE must not run when use_hyde=False even for analytical queries."""
    svc, _, _, hyde_mock = _make_service()

    request = SearchRequest(query="compare revenue trends", search_mode="hybrid", use_hyde=False)
    await svc.search(request)

    hyde_mock.expand_query_to_embedding.assert_not_called()


@pytest.mark.asyncio
async def test_hyde_used_false_in_sparse_mode() -> None:
    """hyde_used must always be False in sparse mode."""
    svc, _, _, _ = _make_service()
    request = SearchRequest(query="compare revenue trends", search_mode="sparse", use_hyde=True)
    response = await svc.search(request)
    assert response.hyde_used is False


# ---------------------------------------------------------------------------
# Response shape
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_response_total_equals_results_length() -> None:
    """SearchResponse.total must equal len(results)."""
    ids = [uuid.uuid4() for _ in range(3)]
    svc, _, _, _ = _make_service(dense_results=[_dense_result(i) for i in ids])

    response = await svc.search(SearchRequest(query="revenue", search_mode="dense"))
    assert response.total == len(response.results)


@pytest.mark.asyncio
async def test_response_echoes_query_and_mode() -> None:
    """SearchResponse must echo the original query and search_mode."""
    svc, _, _, _ = _make_service()
    request = SearchRequest(query="net income", search_mode="sparse")
    response = await svc.search(request)

    assert response.query == "net income"
    assert response.search_mode == "sparse"


@pytest.mark.asyncio
async def test_filters_forwarded_to_dense_search() -> None:
    """Filters in SearchRequest must be passed through to DenseSearchService."""
    doc_id = uuid.uuid4()
    svc, dense_mock, _, _ = _make_service()

    filters = SearchFilters(document_id=doc_id)
    await svc.search(SearchRequest(query="revenue", search_mode="dense", filters=filters))

    call_kwargs = dense_mock.dense_search.call_args
    assert call_kwargs.kwargs["filters"].document_id == doc_id


@pytest.mark.asyncio
async def test_filters_forwarded_to_bm25_search() -> None:
    """Filters in SearchRequest must be passed through to BM25Service."""
    doc_id = uuid.uuid4()
    svc, _, bm25_mock, _ = _make_service()

    filters = SearchFilters(document_id=doc_id)
    await svc.search(SearchRequest(query="revenue", search_mode="sparse", filters=filters))

    call_kwargs = bm25_mock.search.call_args
    assert call_kwargs.kwargs["filters"].document_id == doc_id
