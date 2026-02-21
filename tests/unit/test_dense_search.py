"""
Unit Tests — DenseSearchService

All external dependencies (EmbeddingService, ChunkRepository) are mocked so
these tests run without a database or a loaded ML model.
"""

from __future__ import annotations

import uuid
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.models.chunk import ContentType, SectionType
from src.schemas.search import DenseResult, SearchFilters
from src.services.search import DenseSearchService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_chunk(
    chunk_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    section: SectionType = SectionType.ITEM_1,
    section_title: str = "Business",
    content_raw: str = "Sample content",
    metadata_: dict[str, Any] | None = None,
) -> MagicMock:
    """Build a minimal Chunk-like mock."""
    chunk = MagicMock()
    chunk.id = chunk_id or uuid.uuid4()
    chunk.document_id = document_id or uuid.uuid4()
    chunk.section = section
    chunk.section_title = section_title
    chunk.content_raw = content_raw
    chunk.content_type = ContentType.TEXT
    chunk.metadata_ = metadata_
    return chunk


def _make_service(
    repo_results: list[tuple[MagicMock, float]],
    embedding: list[float] | None = None,
) -> tuple[DenseSearchService, MagicMock, MagicMock]:
    """Return (service, embedding_mock, repo_mock) pre-wired with given results."""
    embedding_svc = MagicMock()
    embedding_svc.embed_texts.return_value = [embedding or [0.1] * 384]

    repo = MagicMock()
    repo.search_by_cosine_similarity = AsyncMock(return_value=repo_results)

    svc = DenseSearchService(embedding_service=embedding_svc, chunk_repo=repo)
    return svc, embedding_svc, repo


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_results_ordered_by_score_descending() -> None:
    """Repository rows are re-sorted descending even if returned out of order."""
    chunk_a = _make_chunk(content_raw="Revenue paragraph")
    chunk_b = _make_chunk(content_raw="Risk factors paragraph")
    chunk_c = _make_chunk(content_raw="MD&A paragraph")

    # Deliberately out-of-order scores
    repo_rows = [(chunk_a, 0.72), (chunk_c, 0.91), (chunk_b, 0.55)]
    svc, _, _ = _make_service(repo_rows)

    results = await svc.dense_search("What is the revenue?", top_k=3)

    assert len(results) == 3
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True), "Results must be descending by score"
    assert results[0].score == pytest.approx(0.91)
    assert results[-1].score == pytest.approx(0.55)


@pytest.mark.asyncio
async def test_top_k_is_respected() -> None:
    """Service passes top_k to the repository unchanged."""
    svc, _, repo = _make_service([])

    await svc.dense_search("query", top_k=7)

    repo.search_by_cosine_similarity.assert_awaited_once()
    call_kwargs = repo.search_by_cosine_similarity.call_args.kwargs
    assert call_kwargs["top_k"] == 7


@pytest.mark.asyncio
async def test_default_top_k_used_when_none() -> None:
    """When top_k is omitted, settings.DEFAULT_TOP_K is forwarded to the repo."""
    svc, _, repo = _make_service([])

    with patch("src.services.search.settings") as mock_settings:
        mock_settings.DEFAULT_TOP_K = 5
        await svc.dense_search("query")

    call_kwargs = repo.search_by_cosine_similarity.call_args.kwargs
    assert call_kwargs["top_k"] == 5


@pytest.mark.asyncio
async def test_filters_forwarded_to_repository() -> None:
    """SearchFilters object is passed through to the repository unchanged."""
    doc_id = uuid.uuid4()
    filters = SearchFilters(
        document_id=doc_id,
        sections=[SectionType.ITEM_1A],
        fiscal_year=2023,
        company="Apple",
    )
    svc, _, repo = _make_service([])

    await svc.dense_search("risk factors", top_k=5, filters=filters)

    call_kwargs = repo.search_by_cosine_similarity.call_args.kwargs
    passed_filters: SearchFilters = call_kwargs["filters"]
    assert passed_filters.document_id == doc_id
    assert passed_filters.sections == [SectionType.ITEM_1A]
    assert passed_filters.fiscal_year == 2023
    assert passed_filters.company == "Apple"


@pytest.mark.asyncio
async def test_empty_query_raises_value_error() -> None:
    """Empty or whitespace-only query must raise ValueError before any I/O."""
    svc, embedding_svc, repo = _make_service([])

    with pytest.raises(ValueError, match="empty"):
        await svc.dense_search("")

    with pytest.raises(ValueError, match="empty"):
        await svc.dense_search("   ")

    # No embedding or DB call should have been made
    embedding_svc.embed_texts.assert_not_called()
    repo.search_by_cosine_similarity.assert_not_awaited()


@pytest.mark.asyncio
async def test_result_fields_mapped_correctly() -> None:
    """DenseResult fields are populated from Chunk + score."""
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    chunk = _make_chunk(
        chunk_id=chunk_id,
        document_id=doc_id,
        section=SectionType.ITEM_7,
        section_title="MD&A",
        content_raw="Operating income increased by 12%.",
        metadata_={"page_approx": 42},
    )
    svc, _, _ = _make_service([(chunk, 0.88)])

    results = await svc.dense_search("operating income", top_k=1)

    assert len(results) == 1
    r: DenseResult = results[0]
    assert r.chunk_id == chunk_id
    assert r.document_id == doc_id
    assert r.content == "Operating income increased by 12%."
    assert r.section == SectionType.ITEM_7
    assert r.section_title == "MD&A"
    assert r.score == pytest.approx(0.88)
    assert r.metadata == {"page_approx": 42}


@pytest.mark.asyncio
async def test_null_metadata_becomes_empty_dict() -> None:
    """Chunks with metadata_=None produce metadata={} in DenseResult."""
    chunk = _make_chunk(metadata_=None)
    svc, _, _ = _make_service([(chunk, 0.5)])

    results = await svc.dense_search("anything", top_k=1)

    assert results[0].metadata == {}


@pytest.mark.asyncio
async def test_null_section_title_becomes_empty_string() -> None:
    """Chunks with section_title=None produce section_title='' in DenseResult."""
    chunk = _make_chunk()
    chunk.section_title = None  # override the mock
    svc, _, _ = _make_service([(chunk, 0.5)])

    results = await svc.dense_search("anything", top_k=1)

    assert results[0].section_title == ""


@pytest.mark.asyncio
async def test_empty_repository_result_returns_empty_list() -> None:
    """No results from the repository → service returns an empty list."""
    svc, _, _ = _make_service([])

    results = await svc.dense_search("obscure query", top_k=5)

    assert results == []


@pytest.mark.asyncio
async def test_embedding_called_with_query_in_list() -> None:
    """embed_texts must receive the query wrapped in a single-element list."""
    svc, embedding_svc, _ = _make_service([])

    await svc.dense_search("What is Apple's revenue?", top_k=3)

    embedding_svc.embed_texts.assert_called_once_with(["What is Apple's revenue?"])
