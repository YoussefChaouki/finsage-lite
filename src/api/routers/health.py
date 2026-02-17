"""
Health Check Router

Provides system health status and dependency checks.
"""

import logging

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.database import get_db
from src.schemas.health import HealthResponse

logger = logging.getLogger(__name__)

router = APIRouter()


@router.get("/health", response_model=HealthResponse)
async def health_check(
    session: AsyncSession = Depends(get_db),
) -> HealthResponse:
    """Health check endpoint.

    Verifies database connectivity via a lightweight ``SELECT 1`` query.

    Returns:
        HealthResponse: System status with dependency availability.
    """
    db_ok = False
    try:
        await session.execute(text("SELECT 1"))
        db_ok = True
    except Exception:
        logger.warning("Database health check failed", exc_info=True)

    return HealthResponse(
        status="ok" if db_ok else "degraded",
        ollama_available=False,  # TODO: Implement Ollama check
        database_available=db_ok,
    )
