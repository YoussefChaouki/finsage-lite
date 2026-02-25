"""
Unit Tests — BM25Service and tokenize_for_bm25

All external dependencies (ChunkRepository, DB session) are mocked so these
tests run entirely in-memory without a database connection.
"""

from __future__ import annotations

import uuid
from types import SimpleNamespace
from typing import Any
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.core.exceptions import IndexNotBuiltError
from src.models.chunk import SectionType
from src.schemas.search import SearchFilters
from src.services.bm25_service import BM25Service, tokenize_for_bm25

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_row(
    chunk_id: uuid.UUID | None = None,
    document_id: uuid.UUID | None = None,
    content_raw: str = "sample financial content",
    section: SectionType = SectionType.ITEM_1,
    section_title: str = "Business",
    metadata: dict[str, Any] | None = None,
    fiscal_year: int = 2023,
    company_name: str = "Apple Inc.",
    ticker: str = "AAPL",
) -> SimpleNamespace:
    """Build a mock DB row as returned by ChunkRepository.get_all_for_bm25."""
    return SimpleNamespace(
        chunk_id=chunk_id or uuid.uuid4(),
        document_id=document_id or uuid.uuid4(),
        content_raw=content_raw,
        section=section,
        section_title=section_title,
        metadata=metadata or {},
        fiscal_year=fiscal_year,
        company_name=company_name,
        ticker=ticker,
    )


async def _build_service(rows: list[SimpleNamespace]) -> BM25Service:
    """Build a BM25Service pre-loaded with *rows*, without touching the DB."""
    service = BM25Service()
    mock_repo = MagicMock()
    mock_repo.get_all_for_bm25 = AsyncMock(return_value=rows)
    mock_db = MagicMock()
    with patch("src.services.bm25_service.ChunkRepository", return_value=mock_repo):
        await service.build_index(mock_db)
    return service


# ---------------------------------------------------------------------------
# tokenize_for_bm25
# ---------------------------------------------------------------------------


def test_tokenize_preserves_financial_terms() -> None:
    """No stemming: ASC, 606, revenue, recognition must survive tokenisation."""
    tokens = tokenize_for_bm25("Revenue recognition under ASC 606")
    assert "revenue" in tokens
    assert "recognition" in tokens
    assert "asc" in tokens
    assert "606" in tokens


def test_tokenize_removes_stopwords() -> None:
    """Common stopwords must be stripped out."""
    tokens = tokenize_for_bm25("Revenue recognition under ASC 606")
    assert "under" not in tokens
    assert "the" not in tokens
    assert "a" not in tokens


def test_tokenize_lowercases() -> None:
    """All returned tokens must be lowercase regardless of input case."""
    tokens = tokenize_for_bm25("EBITDA Goodwill Impairment")
    assert "ebitda" in tokens
    assert "goodwill" in tokens
    assert "impairment" in tokens
    assert all(t == t.lower() for t in tokens)


def test_tokenize_drops_single_chars() -> None:
    """Single-character tokens must be removed."""
    tokens = tokenize_for_bm25("a b c revenue")
    assert "a" not in tokens
    assert "b" not in tokens
    assert "c" not in tokens
    assert "revenue" in tokens


def test_tokenize_handles_hyphenated_terms() -> None:
    """Hyphenated tokens (mark-to-market) must not be split."""
    tokens = tokenize_for_bm25("mark-to-market valuation adjustment")
    # regex \b[a-z0-9][a-z0-9-]*\b keeps internal hyphens
    assert "mark-to-market" in tokens
    assert "valuation" in tokens


def test_tokenize_empty_string_returns_empty() -> None:
    """Empty input must produce an empty list."""
    assert tokenize_for_bm25("") == []


def test_tokenize_whitespace_only_returns_empty() -> None:
    """Whitespace-only input must produce an empty list."""
    assert tokenize_for_bm25("   \t\n  ") == []


# ---------------------------------------------------------------------------
# build_index
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_build_index_marks_is_built() -> None:
    """After build_index, get_stats()['is_built'] must be True."""
    service = await _build_service([_make_row() for _ in range(3)])
    assert service.get_stats()["is_built"] is True


@pytest.mark.asyncio
async def test_build_index_stores_chunk_ids_in_order() -> None:
    """_chunk_ids must mirror the order of rows returned by the repository."""
    ids = [uuid.uuid4() for _ in range(10)]
    rows = [_make_row(chunk_id=cid, content_raw=f"content chunk {i}") for i, cid in enumerate(ids)]
    service = await _build_service(rows)

    assert service._chunk_ids == ids
    assert service.get_stats()["chunk_count"] == 10


@pytest.mark.asyncio
async def test_build_index_empty_corpus() -> None:
    """Empty corpus must result in a built-but-empty index with no errors."""
    service = await _build_service([])

    stats = service.get_stats()
    assert stats["is_built"] is True
    assert stats["chunk_count"] == 0

    # search must return empty list, not raise
    results = await service.search("anything", top_k=5, filters=SearchFilters())
    assert results == []


@pytest.mark.asyncio
async def test_build_index_counts_unique_documents() -> None:
    """document_count must reflect unique document_ids, not total chunk count."""
    doc_a, doc_b = uuid.uuid4(), uuid.uuid4()
    rows = [
        _make_row(document_id=doc_a, content_raw="Revenue streams"),
        _make_row(document_id=doc_a, content_raw="Operating expenses"),
        _make_row(document_id=doc_b, content_raw="Risk factors"),
    ]
    service = await _build_service(rows)
    assert service.get_stats()["document_count"] == 2


@pytest.mark.asyncio
async def test_build_index_replaces_existing_index() -> None:
    """A second build_index call must replace the previous index."""
    service = await _build_service([_make_row(content_raw="old content")])
    assert service.get_stats()["chunk_count"] == 1

    new_rows = [_make_row(content_raw=f"new content {i}") for i in range(5)]
    mock_repo = MagicMock()
    mock_repo.get_all_for_bm25 = AsyncMock(return_value=new_rows)
    mock_db = MagicMock()
    with patch("src.services.bm25_service.ChunkRepository", return_value=mock_repo):
        await service.build_index(mock_db)

    assert service.get_stats()["chunk_count"] == 5


# ---------------------------------------------------------------------------
# search — error cases
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_before_build_raises_index_not_built() -> None:
    """Calling search before build_index must raise IndexNotBuiltError."""
    service = BM25Service()
    with pytest.raises(IndexNotBuiltError):
        await service.search("query", top_k=5, filters=SearchFilters())


@pytest.mark.asyncio
async def test_search_empty_query_raises_value_error() -> None:
    """Empty or whitespace-only query must raise ValueError."""
    service = await _build_service([_make_row(content_raw="some content")])

    with pytest.raises(ValueError, match="empty"):
        await service.search("", top_k=5, filters=SearchFilters())

    with pytest.raises(ValueError, match="empty"):
        await service.search("   ", top_k=5, filters=SearchFilters())


# ---------------------------------------------------------------------------
# search — relevance
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_relevant_chunk_ranked_first() -> None:
    """The chunk most lexically similar to the query must be ranked first."""
    target_id = uuid.uuid4()
    rows = [
        _make_row(
            chunk_id=target_id,
            content_raw="goodwill impairment charge recorded in fiscal year",
        ),
        _make_row(content_raw="revenue from product sales increased"),
        _make_row(content_raw="operating expenses related to research development"),
        _make_row(content_raw="cash flow from operations positive"),
        _make_row(content_raw="total assets on balance sheet"),
    ]
    service = await _build_service(rows)

    results = await service.search("goodwill impairment", top_k=3, filters=SearchFilters())

    assert len(results) > 0
    assert results[0].chunk_id == target_id, "Most relevant chunk must be ranked #1"


@pytest.mark.asyncio
async def test_search_top_k_respected() -> None:
    """search must return at most top_k results."""
    rows = [
        _make_row(content_raw=f"revenue income profit loss goodwill chunk {i}") for i in range(20)
    ]
    service = await _build_service(rows)

    results = await service.search("revenue profit goodwill", top_k=5, filters=SearchFilters())
    assert len(results) <= 5


@pytest.mark.asyncio
async def test_search_scores_non_negative() -> None:
    """Results for a discriminating query must have non-negative BM25 scores.

    BM25Okapi IDF = log(N - freq + 0.5) - log(freq + 0.5), which is positive
    only when the query term appears in fewer than half the corpus. We use a
    corpus where 'earnings' appears in 2 of 5 documents to guarantee IDF > 0
    and therefore scores >= 0 for matching chunks.
    """
    rows = [
        _make_row(content_raw="earnings per share quarterly results"),
        _make_row(content_raw="earnings beat analyst expectations"),
        _make_row(content_raw="total revenue from product sales"),
        _make_row(content_raw="operating expenses research development"),
        _make_row(content_raw="balance sheet total assets liabilities"),
    ]
    service = await _build_service(rows)

    results = await service.search("earnings", top_k=5, filters=SearchFilters())
    assert all(r.bm25_score >= 0 for r in results)


@pytest.mark.asyncio
async def test_search_ranks_sequential_from_one() -> None:
    """Returned results must have sequential 1-based ranks."""
    rows = [
        _make_row(content_raw="revenue recognition policy"),
        _make_row(content_raw="revenue from services segment"),
        _make_row(content_raw="total revenue breakdown by region"),
    ]
    service = await _build_service(rows)

    results = await service.search("revenue", top_k=3, filters=SearchFilters())
    assert [r.rank for r in results] == list(range(1, len(results) + 1))


# ---------------------------------------------------------------------------
# search — field mapping
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_search_result_fields_mapped_correctly() -> None:
    """Every SparseResult field must reflect the stored chunk data."""
    doc_id = uuid.uuid4()
    chunk_id = uuid.uuid4()
    row = _make_row(
        chunk_id=chunk_id,
        document_id=doc_id,
        content_raw="impairment charges recognised in the period",
        section=SectionType.ITEM_8,
        section_title="Financial Statements",
        metadata={"page_approx": 55},
        fiscal_year=2022,
        company_name="Microsoft Corp",
        ticker="MSFT",
    )
    service = await _build_service([row])

    results = await service.search("impairment", top_k=5, filters=SearchFilters())

    assert len(results) == 1
    r = results[0]
    assert r.chunk_id == chunk_id
    assert r.document_id == doc_id
    assert r.content == "impairment charges recognised in the period"
    assert r.section == SectionType.ITEM_8
    assert r.section_title == "Financial Statements"
    assert r.metadata == {"page_approx": 55}
    assert r.rank == 1


@pytest.mark.asyncio
async def test_search_chunk_id_matches_corpus_position() -> None:
    """The chunk_id in each result must correspond to the correct corpus entry."""
    ids = [uuid.uuid4() for _ in range(5)]
    rows = [
        _make_row(chunk_id=ids[0], content_raw="goodwill impairment write-down recorded"),
        _make_row(chunk_id=ids[1], content_raw="revenue growth product segment"),
        _make_row(chunk_id=ids[2], content_raw="operating expenses increased"),
        _make_row(chunk_id=ids[3], content_raw="cash equivalents short-term investments"),
        _make_row(chunk_id=ids[4], content_raw="long-term debt obligations outstanding"),
    ]
    service = await _build_service(rows)

    results = await service.search("goodwill impairment", top_k=1, filters=SearchFilters())

    assert len(results) == 1
    assert results[0].chunk_id == ids[0]


# ---------------------------------------------------------------------------
# search — filtering
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_filter_by_document_id() -> None:
    """Only chunks belonging to the specified document must be returned."""
    target_doc = uuid.uuid4()
    other_doc = uuid.uuid4()
    rows = [
        _make_row(document_id=target_doc, content_raw="revenue growth strategy outlook"),
        _make_row(document_id=other_doc, content_raw="revenue growth competitive position"),
    ]
    service = await _build_service(rows)

    results = await service.search(
        "revenue growth", top_k=5, filters=SearchFilters(document_id=target_doc)
    )

    assert len(results) == 1
    assert results[0].document_id == target_doc


@pytest.mark.asyncio
async def test_filter_by_sections() -> None:
    """Only chunks in the specified sections must be returned."""
    rows = [
        _make_row(section=SectionType.ITEM_1A, content_raw="risk factors cybersecurity threats"),
        _make_row(section=SectionType.ITEM_7, content_raw="risk management discussion analysis"),
    ]
    service = await _build_service(rows)

    results = await service.search(
        "risk", top_k=5, filters=SearchFilters(sections=[SectionType.ITEM_1A])
    )

    assert all(r.section == SectionType.ITEM_1A for r in results)
    assert len(results) == 1


@pytest.mark.asyncio
async def test_filter_by_fiscal_year() -> None:
    """Only chunks from the specified fiscal year must be returned."""
    rows = [
        _make_row(fiscal_year=2023, content_raw="revenue increased significantly"),
        _make_row(fiscal_year=2022, content_raw="revenue declined slightly"),
    ]
    service = await _build_service(rows)

    results = await service.search("revenue", top_k=5, filters=SearchFilters(fiscal_year=2023))

    assert len(results) == 1


@pytest.mark.asyncio
async def test_filter_by_company_name_substring() -> None:
    """Company filter must match case-insensitively on company_name."""
    rows = [
        _make_row(company_name="Apple Inc.", ticker="AAPL", content_raw="iPhone revenue"),
        _make_row(company_name="Microsoft Corp", ticker="MSFT", content_raw="Azure revenue"),
    ]
    service = await _build_service(rows)

    results = await service.search("revenue", top_k=5, filters=SearchFilters(company="apple"))

    assert len(results) == 1
    assert results[0].content == "iPhone revenue"


@pytest.mark.asyncio
async def test_filter_by_ticker() -> None:
    """Company filter must also match case-insensitively on ticker."""
    rows = [
        _make_row(company_name="Apple Inc.", ticker="AAPL", content_raw="product revenue"),
        _make_row(company_name="Microsoft Corp", ticker="MSFT", content_raw="service revenue"),
    ]
    service = await _build_service(rows)

    results = await service.search("revenue", top_k=5, filters=SearchFilters(company="msft"))

    assert len(results) == 1
    assert results[0].content == "service revenue"


@pytest.mark.asyncio
async def test_filter_no_match_returns_empty() -> None:
    """When no chunks pass the filter, an empty list must be returned."""
    rows = [_make_row(fiscal_year=2023, content_raw="net income profit")]
    service = await _build_service(rows)

    results = await service.search("net income", top_k=5, filters=SearchFilters(fiscal_year=2024))

    assert results == []
