"""
Health Check Router

Provides system health status and dependency checks.
"""

from fastapi import APIRouter

from src.schemas.health import HealthResponse

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    """
    Health check endpoint.

    Returns:
        HealthResponse: System status with dependency availability.
    """
    return HealthResponse(
        status="ok",
        ollama_available=False,  # TODO: Implement Ollama check
        database_available=True,  # TODO: Implement DB check
    )
