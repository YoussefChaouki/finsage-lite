"""
Unit tests for health check endpoint.
"""


def test_health_check_structure() -> None:
    """Health check response has required fields."""
    from src.schemas.health import HealthResponse

    response = HealthResponse(status="ok", ollama_available=False, database_available=True)
    assert response.status == "ok"
    assert response.ollama_available is False
    assert response.database_available is True
