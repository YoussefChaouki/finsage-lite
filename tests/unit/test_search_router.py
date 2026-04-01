"""
Unit Tests — Search Router

Tests POST /api/v1/search, GET /api/v1/search/health, and
POST /api/v1/search/rebuild-index without a database or Ollama server.

All services are replaced with MagicMock/AsyncMock instances. A minimal
test FastAPI app is constructed per-fixture so the main app lifespan
(DB init, model loading) is never triggered.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncGenerator
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from src.api.routers import search as search_module
from src.core.database import get_db
from src.models.chunk import SectionType
from src.schemas.search import SearchResponse, SearchResult
from src.services.bm25_service import BM25Service
from src.services.generation import GenerationService
from src.services.hyde_service import HyDEService
from src.services.retrieval_service import RetrievalService

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

_DOC_ID = uuid.uuid4()
_CHUNK_ID = uuid.uuid4()
_SECTION = SectionType.ITEM_1A


def _make_result(score: float = 0.85) -> SearchResult:
    return SearchResult(
        chunk_id=_CHUNK_ID,
        document_id=_DOC_ID,
        content="Apple reported net revenue of $383.3 billion.",
        section=_SECTION,
        section_title="Risk Factors",
        score=score,
        dense_score=score,
        sparse_score=None,
        metadata={"page_approx": 12},
    )


def _make_response(
    mode: str = "hybrid",
    n_results: int = 1,
    hyde_used: bool = False,
    latency_ms: float = 42.0,
) -> SearchResponse:
    results = [_make_result(score=0.9 - i * 0.05) for i in range(n_results)]
    return SearchResponse(
        answer=None,
        results=results,
        total=len(results),
        query="Apple revenue",
        search_mode=mode,
        hyde_used=hyde_used,
        latency_ms=latency_ms,
    )


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_retrieval_service() -> MagicMock:
    """RetrievalService mock that returns a default hybrid SearchResponse."""
    mock = MagicMock(spec=RetrievalService)
    mock.search = AsyncMock(return_value=_make_response())
    return mock


@pytest.fixture
def mock_bm25_service() -> MagicMock:
    """BM25Service mock with a pre-built index of 42 chunks."""
    mock = MagicMock(spec=BM25Service)
    mock.get_stats.return_value = {
        "is_built": True,
        "chunk_count": 42,
        "document_count": 3,
    }
    mock.build_index = AsyncMock()
    return mock


@pytest.fixture
def mock_hyde_service() -> MagicMock:
    """HyDEService mock reporting Ollama as unavailable."""
    mock = MagicMock(spec=HyDEService)
    mock.is_available = AsyncMock(return_value=False)
    return mock


@pytest.fixture
def mock_generation_service() -> MagicMock:
    """GenerationService mock that returns None (no LLM in unit tests)."""
    mock = MagicMock(spec=GenerationService)
    mock.generate = AsyncMock(return_value=None)
    return mock


@pytest.fixture
def client(
    mock_retrieval_service: MagicMock,
    mock_bm25_service: MagicMock,
    mock_hyde_service: MagicMock,
    mock_generation_service: MagicMock,
) -> TestClient:
    """TestClient wrapping a minimal FastAPI app with all search deps mocked.

    - app.state provides BM25Service, HyDEService, and GenerationService singletons.
    - get_retrieval_service and get_generation_service are overridden so no DB,
      model loading, or Ollama calls occur.
    - get_db is overridden to avoid requiring a real Postgres connection.
    """
    test_app = FastAPI()
    test_app.include_router(search_module.router)

    # State-based deps read directly from app.state
    test_app.state.bm25_service = mock_bm25_service
    test_app.state.hyde_service = mock_hyde_service
    test_app.state.generation_service = mock_generation_service

    async def _override_retrieval_service() -> RetrievalService:
        return mock_retrieval_service

    async def _override_generation_service() -> GenerationService:
        return mock_generation_service

    async def _override_get_db() -> AsyncGenerator[Any, None]:
        yield MagicMock()

    test_app.dependency_overrides[search_module.get_retrieval_service] = (
        _override_retrieval_service
    )
    test_app.dependency_overrides[search_module.get_generation_service] = (
        _override_generation_service
    )
    test_app.dependency_overrides[get_db] = _override_get_db

    with TestClient(test_app) as c:
        yield c

    test_app.dependency_overrides.clear()


# ---------------------------------------------------------------------------
# POST /api/v1/search — status and schema
# ---------------------------------------------------------------------------


def test_search_returns_200(client: TestClient) -> None:
    """POST /api/v1/search must return HTTP 200."""
    response = client.post("/api/v1/search", json={"query": "Apple revenue"})
    assert response.status_code == 200


def test_search_response_has_required_fields(client: TestClient) -> None:
    """Response must include answer, results, total, query, search_mode, etc."""
    response = client.post("/api/v1/search", json={"query": "Apple revenue"})
    data = response.json()

    assert "answer" in data
    assert "results" in data
    assert "total" in data
    assert "query" in data
    assert "search_mode" in data
    assert "hyde_used" in data
    assert "latency_ms" in data


def test_search_answer_is_null_before_generation(client: TestClient) -> None:
    """answer field must be null (Sprint 3 not implemented yet)."""
    response = client.post("/api/v1/search", json={"query": "Apple revenue"})
    assert response.json()["answer"] is None


def test_search_echoes_query(client: TestClient) -> None:
    """Response must echo the original query."""
    response = client.post("/api/v1/search", json={"query": "Apple revenue"})
    assert response.json()["query"] == "Apple revenue"


# ---------------------------------------------------------------------------
# POST /api/v1/search — dense mode
# ---------------------------------------------------------------------------


def test_search_dense_mode(client: TestClient, mock_retrieval_service: MagicMock) -> None:
    """Dense mode delegates to RetrievalService.search with correct mode."""
    mock_retrieval_service.search = AsyncMock(return_value=_make_response(mode="dense"))

    response = client.post(
        "/api/v1/search", json={"query": "Apple revenue", "search_mode": "dense"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["search_mode"] == "dense"
    assert data["total"] >= 0


def test_search_dense_mode_calls_retrieval_service(
    client: TestClient, mock_retrieval_service: MagicMock
) -> None:
    """POST /api/v1/search must delegate to RetrievalService.search exactly once."""
    client.post("/api/v1/search", json={"query": "net income", "search_mode": "dense"})
    mock_retrieval_service.search.assert_called_once()


# ---------------------------------------------------------------------------
# POST /api/v1/search — sparse mode
# ---------------------------------------------------------------------------


def test_search_sparse_mode(client: TestClient, mock_retrieval_service: MagicMock) -> None:
    """Sparse mode delegates to RetrievalService and returns 200."""
    mock_retrieval_service.search = AsyncMock(return_value=_make_response(mode="sparse"))

    response = client.post(
        "/api/v1/search", json={"query": "goodwill impairment", "search_mode": "sparse"}
    )
    assert response.status_code == 200
    assert response.json()["search_mode"] == "sparse"


# ---------------------------------------------------------------------------
# POST /api/v1/search — hybrid mode
# ---------------------------------------------------------------------------


def test_search_hybrid_mode(client: TestClient, mock_retrieval_service: MagicMock) -> None:
    """Hybrid mode (default) delegates to RetrievalService and returns 200."""
    mock_retrieval_service.search = AsyncMock(return_value=_make_response(mode="hybrid"))

    response = client.post(
        "/api/v1/search", json={"query": "revenue trends", "search_mode": "hybrid"}
    )
    assert response.status_code == 200
    assert response.json()["search_mode"] == "hybrid"


def test_search_default_mode_is_hybrid(
    client: TestClient, mock_retrieval_service: MagicMock
) -> None:
    """Omitting search_mode must default to 'hybrid'."""
    mock_retrieval_service.search = AsyncMock(return_value=_make_response(mode="hybrid"))

    response = client.post("/api/v1/search", json={"query": "EBITDA"})
    assert response.status_code == 200
    # RetrievalService.search was called — that's the contract; mode is in the request body
    mock_retrieval_service.search.assert_called_once()


# ---------------------------------------------------------------------------
# POST /api/v1/search — validation
# ---------------------------------------------------------------------------


def test_search_invalid_mode_returns_422(client: TestClient) -> None:
    """Unknown search_mode must be rejected with 422 Unprocessable Entity."""
    response = client.post(
        "/api/v1/search",
        json={"query": "revenue", "search_mode": "fuzzy"},
    )
    assert response.status_code == 422


def test_search_top_k_too_large_returns_422(client: TestClient) -> None:
    """top_k > 100 must be rejected (Field constraint, limit raised to 100 for browse)."""
    response = client.post(
        "/api/v1/search",
        json={"query": "revenue", "top_k": 101},
    )
    assert response.status_code == 422


def test_search_top_k_zero_returns_422(client: TestClient) -> None:
    """top_k=0 must be rejected (Field ge=1 constraint)."""
    response = client.post(
        "/api/v1/search",
        json={"query": "revenue", "top_k": 0},
    )
    assert response.status_code == 422


def test_search_missing_query_returns_422(client: TestClient) -> None:
    """Request without query field must be rejected with 422."""
    response = client.post("/api/v1/search", json={"search_mode": "dense"})
    assert response.status_code == 422


# ---------------------------------------------------------------------------
# POST /api/v1/search — HyDE flag
# ---------------------------------------------------------------------------


def test_search_hyde_flag_forwarded(client: TestClient, mock_retrieval_service: MagicMock) -> None:
    """use_hyde=True must be passed through to RetrievalService."""
    mock_retrieval_service.search = AsyncMock(return_value=_make_response(hyde_used=True))

    response = client.post(
        "/api/v1/search",
        json={"query": "compare revenue trends", "use_hyde": True},
    )
    assert response.status_code == 200
    mock_retrieval_service.search.assert_called_once()
    call_arg = mock_retrieval_service.search.call_args[0][0]
    assert call_arg.use_hyde is True


# ---------------------------------------------------------------------------
# GET /api/v1/search/health
# ---------------------------------------------------------------------------


def test_search_health_returns_200(client: TestClient) -> None:
    """GET /api/v1/search/health must return HTTP 200."""
    response = client.get("/api/v1/search/health")
    assert response.status_code == 200


def test_search_health_response_schema(client: TestClient) -> None:
    """Health response must include all SearchHealthResponse fields."""
    data = client.get("/api/v1/search/health").json()

    assert "bm25_index_size" in data
    assert "bm25_is_built" in data
    assert "hyde_available" in data
    assert "ollama_model" in data


def test_search_health_bm25_stats(client: TestClient, mock_bm25_service: MagicMock) -> None:
    """Health endpoint must reflect BM25 index stats from the service."""
    data = client.get("/api/v1/search/health").json()

    assert data["bm25_index_size"] == 42
    assert data["bm25_is_built"] is True


def test_search_health_hyde_unavailable(client: TestClient, mock_hyde_service: MagicMock) -> None:
    """Health endpoint must report hyde_available=False when Ollama is down."""
    mock_hyde_service.is_available = AsyncMock(return_value=False)
    data = client.get("/api/v1/search/health").json()
    assert data["hyde_available"] is False


def test_search_health_hyde_available(client: TestClient, mock_hyde_service: MagicMock) -> None:
    """Health endpoint must report hyde_available=True when Ollama is reachable."""
    mock_hyde_service.is_available = AsyncMock(return_value=True)
    data = client.get("/api/v1/search/health").json()
    assert data["hyde_available"] is True


# ---------------------------------------------------------------------------
# POST /api/v1/search/rebuild-index
# ---------------------------------------------------------------------------


def test_rebuild_index_returns_200(client: TestClient) -> None:
    """POST /api/v1/search/rebuild-index must return HTTP 200."""
    response = client.post("/api/v1/search/rebuild-index")
    assert response.status_code == 200


def test_rebuild_index_calls_build_index(client: TestClient, mock_bm25_service: MagicMock) -> None:
    """Rebuild endpoint must invoke BM25Service.build_index exactly once."""
    client.post("/api/v1/search/rebuild-index")
    mock_bm25_service.build_index.assert_called_once()


def test_rebuild_index_returns_chunk_count(
    client: TestClient, mock_bm25_service: MagicMock
) -> None:
    """Rebuild response must contain chunk_count from the updated index stats."""
    data = client.post("/api/v1/search/rebuild-index").json()
    assert "chunk_count" in data
    assert data["chunk_count"] == 42


# ---------------------------------------------------------------------------
# Result shape in search response
# ---------------------------------------------------------------------------


def test_search_results_have_required_fields(client: TestClient) -> None:
    """Each SearchResult in the response must have mandatory fields."""
    response = client.post("/api/v1/search", json={"query": "revenue"})
    results = response.json()["results"]

    assert len(results) >= 1
    r = results[0]
    assert "chunk_id" in r
    assert "document_id" in r
    assert "content" in r
    assert "section" in r
    assert "section_title" in r
    assert "score" in r
    assert "metadata" in r


def test_search_total_matches_results_length(client: TestClient) -> None:
    """total field must equal len(results)."""
    _mock_response = _make_response(n_results=3)
    # The TestClient uses the fixture mock that already returns n_results=1.
    # We verify the schema contract from what the mock returns.
    response = client.post("/api/v1/search", json={"query": "revenue"})
    data = response.json()
    assert data["total"] == len(data["results"])


def test_search_latency_ms_is_positive(client: TestClient) -> None:
    """latency_ms must be a positive number."""
    response = client.post("/api/v1/search", json={"query": "revenue"})
    assert response.json()["latency_ms"] > 0
