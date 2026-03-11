"""
Integration Tests — Table Extraction E2E

Validates that financial HTML tables from a real SEC 10-K filing are correctly
extracted, indexed as TABLE chunks, and retrievable via the search engine.

Prerequisites:
  - make docker-up   (FastAPI + PostgreSQL running at localhost:8000)
  - AAPL FY2024 already ingested:
      curl -X POST http://localhost:8000/api/v1/documents/ingest \\
           -H 'Content-Type: application/json' \\
           -d '{"ticker":"AAPL","fiscal_year":2024}'

Run with: make test-int
"""

import json
import re

import httpx
import pytest

BASE_SEARCH = "/api/v1/search"
BASE_DOCS = "/api/v1/documents"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _find_aapl_fy2024(api_client: httpx.Client) -> dict | None:
    """Return the AAPL FY2024 document entry from the list endpoint, or None."""
    resp = api_client.get(BASE_DOCS)
    if resp.status_code != 200:
        return None
    for doc in resp.json().get("documents", []):
        if doc.get("ticker") == "AAPL" and doc.get("fiscal_year") == 2024:
            return doc
    return None


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_ingested_document_has_table_chunks(api_client: httpx.Client) -> None:
    """After ingestion, at least one TABLE chunk must exist for AAPL FY2024.

    TABLE chunks are identified by the presence of ``table_title`` in their
    metadata, which is set exclusively by ``SectionChunker.chunk_tables()``.
    A broad hybrid search surfaces financial-section chunks with top_k=20.
    """
    doc = _find_aapl_fy2024(api_client)
    if doc is None:
        pytest.skip("AAPL FY2024 not ingested — run POST /api/v1/documents/ingest first")

    response = api_client.post(
        BASE_SEARCH,
        json={
            "query": "financial statements revenue income net sales",
            "search_mode": "hybrid",
            "top_k": 20,
            "filters": {"document_id": doc["id"]},
        },
    )
    assert response.status_code == 200

    results = response.json()["results"]
    table_results = [r for r in results if "table_title" in r.get("metadata", {})]

    assert len(table_results) >= 1, (
        f"Expected ≥1 TABLE chunk in top-20 results, found 0. "
        f"Total results: {len(results)}. "
        "Ensure AAPL was ingested after the chunk_tables() pipeline was added."
    )


@pytest.mark.integration
def test_revenue_query_returns_financial_data(api_client: httpx.Client) -> None:
    """Hybrid search for Apple revenue must return ITEM_7/ITEM_8 results with dollar figures.

    Validates:
    - At least one result comes from a financial section (ITEM_7 or ITEM_8).
    - At least one result content contains a dollar figure (regex ``$[digit]``).
    """
    doc = _find_aapl_fy2024(api_client)
    if doc is None:
        pytest.skip("AAPL FY2024 not ingested — run POST /api/v1/documents/ingest first")

    response = api_client.post(
        BASE_SEARCH,
        json={
            "query": "Apple total net revenue",
            "search_mode": "hybrid",
            "top_k": 10,
            "filters": {"document_id": doc["id"]},
        },
    )
    assert response.status_code == 200

    results = response.json()["results"]
    assert len(results) >= 1, "Expected at least one result for 'Apple total net revenue'"

    financial_sections = {"ITEM_7", "ITEM_8"}
    financial_results = [r for r in results if r["section"] in financial_sections]
    assert len(financial_results) >= 1, (
        f"Expected at least one result from ITEM_7 or ITEM_8. "
        f"Sections returned: {[r['section'] for r in results]}"
    )

    dollar_re = re.compile(r"\$[\d]")
    has_dollar = any(dollar_re.search(r["content"]) for r in results)
    assert has_dollar, (
        "Expected at least one result containing a dollar figure (e.g. '$391'). "
        f"Content samples: {[r['content'][:100] for r in results[:3]]}"
    )


@pytest.mark.integration
def test_table_chunk_metadata_has_table_data(api_client: httpx.Client) -> None:
    """TABLE chunks returned by search must carry both ``table_title`` and ``table_data``.

    Validates:
    - ``metadata["table_title"]`` is a non-empty string.
    - ``metadata["table_data"]`` is a valid JSON string with ``headers`` and ``rows`` keys.
    """
    doc = _find_aapl_fy2024(api_client)
    if doc is None:
        pytest.skip("AAPL FY2024 not ingested — run POST /api/v1/documents/ingest first")

    response = api_client.post(
        BASE_SEARCH,
        json={
            "query": "revenue net sales operating income financial statements",
            "search_mode": "hybrid",
            "top_k": 20,
            "filters": {"document_id": doc["id"]},
        },
    )
    assert response.status_code == 200

    results = response.json()["results"]
    table_results = [r for r in results if "table_title" in r.get("metadata", {})]

    if not table_results:
        pytest.skip(
            "No TABLE chunks retrieved for this query. "
            "Rebuild the BM25 index (POST /api/v1/search/rebuild-index) and retry."
        )

    for chunk in table_results:
        metadata = chunk["metadata"]

        assert "table_title" in metadata, f"Missing table_title. metadata keys: {list(metadata)}"
        assert isinstance(metadata["table_title"], str) and metadata["table_title"]

        assert "table_data" in metadata, f"Missing table_data. metadata keys: {list(metadata)}"
        parsed = json.loads(metadata["table_data"])
        assert "headers" in parsed, f"table_data missing 'headers': {parsed}"
        assert "rows" in parsed, f"table_data missing 'rows': {parsed}"
        assert isinstance(parsed["rows"], list)
