"""
Health Check Router

Provides system health status and dependency checks.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.api.routers.search import get_hyde_service
from src.core.database import get_db
from src.schemas.health import HealthResponse
from src.services.hyde_service import HyDEService

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(
    session: AsyncSession = Depends(get_db),
    hyde_service: HyDEService = Depends(get_hyde_service),
) -> HealthResponse:
    """Health check endpoint.

    Verifies database connectivity via a lightweight ``SELECT 1`` query and
    probes Ollama reachability via the HyDEService.

    Args:
        session: Database session (injected).
        hyde_service: HyDE service used to probe Ollama reachability.

    Returns:
        HealthResponse: System status with dependency availability.
    """
    db_ok = False
    try:
        await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        logger.warning("Database health check failed", exc_info=True)

    ollama_ok = await hyde_service.is_available()

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        ollama_available=ollama_ok,
        database_available=db_ok,
    )
