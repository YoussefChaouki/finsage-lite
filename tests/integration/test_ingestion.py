"""
Ingestion Integration Tests

End-to-end tests requiring Docker (PostgreSQL + API) and real SEC EDGAR calls.
Run with: make docker-up && make test-int
"""

import uuid

import httpx
import pytest


@pytest.mark.integration
class TestIngestionEndpoint:
    """Integration tests for POST /api/v1/documents/ingest."""

    def test_ingest_aapl_fy2024(self, api_client: httpx.Client) -> None:
        """Ingest AAPL FY2024 end-to-end: EDGAR → parse → chunk → embed → store."""
        response = api_client.post(
            "/api/v1/documents/ingest",
            json={"ticker": "AAPL", "fiscal_year": 2024},
            timeout=120.0,
        )
        assert response.status_code == 200, f"Ingestion failed: {response.text}"

        data = response.json()
        assert data["status"] in ("created", "already_exists")
        assert "document_id" in data
        assert data["document_id"] is not None

        # Store document_id for subsequent tests
        self.__class__._document_id = data["document_id"]

    def test_ingest_duplicate_returns_existing(self, api_client: httpx.Client) -> None:
        """Second ingestion of same ticker+year returns already_exists."""
        response = api_client.post(
            "/api/v1/documents/ingest",
            json={"ticker": "AAPL", "fiscal_year": 2024},
            timeout=120.0,
        )
        assert response.status_code == 200

        data = response.json()
        assert data["status"] == "already_exists"

    def test_ingest_invalid_ticker(self, api_client: httpx.Client) -> None:
        """Invalid ticker returns 404."""
        response = api_client.post(
            "/api/v1/documents/ingest",
            json={"ticker": "ZZZZZZZ", "fiscal_year": 2024},
            timeout=30.0,
        )
        assert response.status_code == 404

    def test_ingest_missing_fields(self, api_client: httpx.Client) -> None:
        """Missing required fields return 422."""
        response = api_client.post(
            "/api/v1/documents/ingest",
            json={"ticker": "AAPL"},
            timeout=10.0,
        )
        assert response.status_code == 422


@pytest.mark.integration
class TestDocumentListEndpoint:
    """Integration tests for GET /api/v1/documents."""

    def test_list_documents(self, api_client: httpx.Client) -> None:
        """List endpoint returns at least one document after ingestion."""
        response = api_client.get("/api/v1/documents")
        assert response.status_code == 200

        data = response.json()
        assert data["total"] >= 1
        assert len(data["documents"]) >= 1

        doc = data["documents"][0]
        assert "id" in doc
        assert "company_name" in doc
        assert "ticker" in doc
        assert "num_chunks" in doc
        assert "sections" in doc


@pytest.mark.integration
class TestDocumentDetailEndpoint:
    """Integration tests for GET /api/v1/documents/{document_id}."""

    def test_get_document_detail(self, api_client: httpx.Client) -> None:
        """Document detail returns full information including sections."""
        # First, get a document ID from the list
        list_response = api_client.get("/api/v1/documents")
        assert list_response.status_code == 200

        documents = list_response.json()["documents"]
        assert len(documents) >= 1

        doc_id = documents[0]["id"]

        # Fetch detail
        response = api_client.get(f"/api/v1/documents/{doc_id}")
        assert response.status_code == 200

        data = response.json()
        assert data["id"] == doc_id
        assert data["processed"] is True
        assert data["num_chunks"] > 0
        assert len(data["sections"]) > 0

        # Verify section structure
        for section in data["sections"]:
            assert "section" in section
            assert "section_title" in section
            assert "num_chunks" in section
            assert section["num_chunks"] > 0

    def test_get_document_not_found(self, api_client: httpx.Client) -> None:
        """Non-existent document ID returns 404."""
        fake_id = str(uuid.uuid4())
        response = api_client.get(f"/api/v1/documents/{fake_id}")
        assert response.status_code == 404

    def test_get_document_invalid_uuid(self, api_client: httpx.Client) -> None:
        """Invalid UUID format returns 422."""
        response = api_client.get("/api/v1/documents/not-a-uuid")
        assert response.status_code == 422
