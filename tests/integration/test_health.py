"""
Integration tests for health check endpoint.

Requires a running Docker stack (make docker-up).
"""

import httpx
import pytest


@pytest.mark.integration
def test_health_endpoint(api_client: httpx.Client) -> None:
    """Health endpoint returns 200 with expected structure."""
    response = api_client.get("/health")
    assert response.status_code == 200

    data = response.json()
    assert data["status"] == "ok"
    assert "ollama_available" in data
    assert "database_available" in data
