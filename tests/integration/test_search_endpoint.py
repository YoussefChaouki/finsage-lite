"""
Integration Tests — Search Endpoint

Requires a running Docker stack (make docker-up) with the API server and
PostgreSQL. Tests validate HTTP structure and response schema for all three
search modes. Results may be empty when no documents have been ingested yet.

Run with: make test-int
"""

import httpx
import pytest

BASE_SEARCH = "/api/v1/search"


# ---------------------------------------------------------------------------
# POST /api/v1/search — three retrieval modes
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_search_dense_mode_returns_200(api_client: httpx.Client) -> None:
    """Dense search must return 200 with valid schema."""
    response = api_client.post(
        BASE_SEARCH,
        json={"query": "Apple revenue", "search_mode": "dense", "top_k": 5},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["search_mode"] == "dense"
    assert isinstance(data["results"], list)
    assert isinstance(data["total"], int)
    assert data["total"] == len(data["results"])
    assert data["hyde_used"] is False
    assert data["latency_ms"] > 0
    assert data["answer"] is None or isinstance(data["answer"], str)


@pytest.mark.integration
def test_search_sparse_mode_returns_200(api_client: httpx.Client) -> None:
    """Sparse (BM25) search must return 200 with valid schema."""
    response = api_client.post(
        BASE_SEARCH,
        json={"query": "goodwill impairment risk", "search_mode": "sparse", "top_k": 5},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["search_mode"] == "sparse"
    assert isinstance(data["results"], list)
    assert data["total"] == len(data["results"])
    assert data["latency_ms"] > 0
    assert data["answer"] is None or isinstance(data["answer"], str)


@pytest.mark.integration
def test_search_hybrid_mode_returns_200(api_client: httpx.Client) -> None:
    """Hybrid (BM25 + dense + RRF) search must return 200 with valid schema."""
    response = api_client.post(
        BASE_SEARCH,
        json={"query": "net income operating margin", "search_mode": "hybrid", "top_k": 5},
    )
    assert response.status_code == 200

    data = response.json()
    assert data["search_mode"] == "hybrid"
    assert isinstance(data["results"], list)
    assert data["total"] == len(data["results"])
    assert data["latency_ms"] > 0
    assert data["answer"] is None or isinstance(data["answer"], str)


@pytest.mark.integration
def test_search_default_mode_is_hybrid(api_client: httpx.Client) -> None:
    """Omitting search_mode must default to hybrid."""
    response = api_client.post(BASE_SEARCH, json={"query": "EBITDA"})
    assert response.status_code == 200
    assert response.json()["search_mode"] == "hybrid"


# ---------------------------------------------------------------------------
# POST /api/v1/search — top_k enforcement
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_search_top_k_respected(api_client: httpx.Client) -> None:
    """Returned results must not exceed top_k."""
    response = api_client.post(
        BASE_SEARCH,
        json={"query": "revenue growth", "search_mode": "hybrid", "top_k": 3},
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["results"]) <= 3
    assert data["total"] <= 3


# ---------------------------------------------------------------------------
# POST /api/v1/search — result item schema
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_search_result_item_schema(api_client: httpx.Client) -> None:
    """Each result item must expose the full SearchResult schema fields."""
    response = api_client.post(
        BASE_SEARCH,
        json={"query": "risk factors", "search_mode": "hybrid", "top_k": 5},
    )
    assert response.status_code == 200

    results = response.json()["results"]
    for item in results:
        assert "chunk_id" in item
        assert "document_id" in item
        assert "content" in item
        assert "section" in item
        assert "section_title" in item
        assert "score" in item
        assert "metadata" in item
        assert 0.0 <= item["score"] <= 1.0


# ---------------------------------------------------------------------------
# POST /api/v1/search — validation errors
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_search_invalid_mode_returns_422(api_client: httpx.Client) -> None:
    """Unknown search_mode must be rejected with 422."""
    response = api_client.post(BASE_SEARCH, json={"query": "revenue", "search_mode": "fuzzy"})
    assert response.status_code == 422


@pytest.mark.integration
def test_search_top_k_out_of_range_returns_422(api_client: httpx.Client) -> None:
    """top_k=0 and top_k=21 must both be rejected with 422."""
    for bad_k in (0, 21):
        response = api_client.post(BASE_SEARCH, json={"query": "revenue", "top_k": bad_k})
        assert response.status_code == 422, f"Expected 422 for top_k={bad_k}"


# ---------------------------------------------------------------------------
# GET /api/v1/search/health
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_search_health_returns_200(api_client: httpx.Client) -> None:
    """GET /api/v1/search/health must return 200."""
    response = api_client.get(f"{BASE_SEARCH}/health")
    assert response.status_code == 200


@pytest.mark.integration
def test_search_health_response_schema(api_client: httpx.Client) -> None:
    """Health response must expose all SearchHealthResponse fields."""
    data = api_client.get(f"{BASE_SEARCH}/health").json()

    assert "bm25_index_size" in data
    assert "bm25_is_built" in data
    assert "hyde_available" in data
    assert "ollama_model" in data
    assert isinstance(data["bm25_index_size"], int)
    assert isinstance(data["bm25_is_built"], bool)
    assert isinstance(data["hyde_available"], bool)
    assert isinstance(data["ollama_model"], str)


@pytest.mark.integration
def test_search_health_bm25_is_built(api_client: httpx.Client) -> None:
    """BM25 index must report as built after startup."""
    data = api_client.get(f"{BASE_SEARCH}/health").json()
    assert data["bm25_is_built"] is True


# ---------------------------------------------------------------------------
# POST /api/v1/search/rebuild-index
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_rebuild_index_returns_200(api_client: httpx.Client) -> None:
    """POST /api/v1/search/rebuild-index must return 200 with chunk_count."""
    response = api_client.post(f"{BASE_SEARCH}/rebuild-index")
    assert response.status_code == 200

    data = response.json()
    assert "chunk_count" in data
    assert isinstance(data["chunk_count"], int)
    assert data["chunk_count"] >= 0


@pytest.mark.integration
def test_rebuild_index_bm25_still_usable(api_client: httpx.Client) -> None:
    """After rebuild, search must still return 200."""
    api_client.post(f"{BASE_SEARCH}/rebuild-index")

    response = api_client.post(
        BASE_SEARCH,
        json={"query": "revenue", "search_mode": "sparse"},
    )
    assert response.status_code == 200
