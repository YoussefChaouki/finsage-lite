"""
Database Configuration

Async SQLAlchemy 2.0 setup with connection pooling and session management.
Uses asyncpg as the PostgreSQL driver for non-blocking I/O.
Includes pgvector extension initialization.
"""

from collections.abc import AsyncGenerator

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

from src.core.config import settings

# Async engine with connection pooling (default pool_size=5, max_overflow=10)
engine = create_async_engine(settings.DATABASE_URL, echo=False)

# expire_on_commit=False: prevents implicit I/O after commit when accessing attributes
AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)


async def get_db() -> AsyncGenerator[AsyncSession, None]:
    """
    FastAPI dependency that provides a database session per request.

    Yields:
        AsyncSession: Scoped to the request lifecycle. Automatically closed
        after the request completes (including on exceptions).
    """
    async with AsyncSessionLocal() as session:
        yield session


async def init_db() -> None:
    """
    Initialize database extensions (pgvector).
    Should be called once at application startup.
    """
    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
