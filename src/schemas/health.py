"""
Health Check Schemas

Pydantic schemas for health check endpoints.
"""

from pydantic import BaseModel


class HealthResponse(BaseModel):
    """Health check response schema."""

    status: str
    ollama_available: bool = False
    database_available: bool = True
