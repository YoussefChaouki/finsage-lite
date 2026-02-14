"""
Integration tests for EmbeddingService + pgvector.

Tests the full pipeline: embed chunks → store in DB → retrieve by cosine similarity.
Requires a running Docker stack with migrations applied (make docker-up && make migrate).
"""

import uuid
from datetime import date

import httpx
import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession, async_sessionmaker, create_async_engine

BASE_URL = "http://localhost:8000"


@pytest.fixture(scope="module")
def _require_db() -> None:
    """Skip the module if the API (and therefore DB) is not reachable."""
    try:
        res = httpx.get(f"{BASE_URL}/health", timeout=3.0)
        if res.status_code != 200:
            pytest.skip("API not healthy")
    except httpx.RequestError:
        pytest.skip("API unreachable — Docker likely not running")


@pytest_asyncio.fixture()
async def db_session(
    _require_db: None,
) -> async_sessionmaker[AsyncSession]:
    """Return a fresh async session factory with its own engine.

    Creates a dedicated engine per test to avoid event-loop conflicts
    with the application-level engine (which is bound at import time).
    Ensures pgvector extension and tables exist before yielding.
    """
    from sqlalchemy import text

    import src.models.chunk  # noqa: F401
    import src.models.document  # noqa: F401
    from src.core.config import settings
    from src.models.base import Base

    engine = create_async_engine(settings.DATABASE_URL, echo=False)

    async with engine.begin() as conn:
        await conn.execute(text("CREATE EXTENSION IF NOT EXISTS vector"))
        await conn.run_sync(Base.metadata.create_all)

    factory: async_sessionmaker[AsyncSession] = async_sessionmaker(engine, expire_on_commit=False)

    yield factory  # type: ignore[misc]

    await engine.dispose()


@pytest.mark.asyncio()
async def test_embed_and_store_creates_chunks_in_db(
    db_session: async_sessionmaker[AsyncSession],
) -> None:
    """embed_and_store persists chunks with correct embeddings."""
    from src.models.chunk import ContentType, SectionType
    from src.models.document import Document
    from src.repositories.chunk import ChunkRepository
    from src.schemas.chunking import ChunkData
    from src.services.embedding import EmbeddingService

    service = EmbeddingService(batch_size=4)
    doc_id = uuid.uuid4()

    chunks = [
        ChunkData(
            section=SectionType.ITEM_7,
            section_title="MD&A",
            content_type=ContentType.TEXT,
            content_raw="Revenue increased 12% year-over-year.",
            content_context=(
                "[Test Corp | 10-K FY2024 | MD&A]\n\nRevenue increased 12% year-over-year."
            ),
            chunk_index=0,
            metadata={"company": "Test Corp", "fiscal_year": 2024},
        ),
        ChunkData(
            section=SectionType.ITEM_1A,
            section_title="Risk Factors",
            content_type=ContentType.TEXT,
            content_raw="Supply chain risks may impact operations.",
            content_context=(
                "[Test Corp | 10-K FY2024 | Risk Factors]\n\n"
                "Supply chain risks may impact operations."
            ),
            chunk_index=1,
            metadata={"company": "Test Corp", "fiscal_year": 2024},
        ),
    ]

    async with db_session() as session:
        doc = Document(
            id=doc_id,
            company_name="Test Corp",
            cik="0001234567",
            ticker="TEST",
            filing_type="10-K",
            filing_date=date(2024, 3, 15),
            fiscal_year=2024,
            accession_no=f"test-{uuid.uuid4().hex[:8]}",
            source_url="https://example.com/test",
        )
        session.add(doc)
        await session.flush()

        stored = await service.embed_and_store(chunks, doc_id, session)
        await session.commit()

        assert len(stored) == 2

        # Verify chunks are in DB
        repo = ChunkRepository(session)
        db_chunks = await repo.get_by_document_id(doc_id)
        assert len(db_chunks) == 2
        for chunk in db_chunks:
            assert chunk.embedding is not None
            assert len(chunk.embedding) == 384

        # Cleanup
        await repo.delete_by_document_id(doc_id)
        from sqlalchemy import text

        await session.execute(text("DELETE FROM documents WHERE id = :id"), {"id": doc_id})
        await session.commit()


@pytest.mark.asyncio()
async def test_cosine_similarity_search_returns_relevant_chunk(
    db_session: async_sessionmaker[AsyncSession],
) -> None:
    """Inserting chunks and querying returns the most relevant one."""
    from src.models.chunk import ContentType, SectionType
    from src.models.document import Document
    from src.repositories.chunk import ChunkRepository
    from src.schemas.chunking import ChunkData
    from src.services.embedding import EmbeddingService

    service = EmbeddingService(batch_size=4)
    doc_id = uuid.uuid4()

    chunks = [
        ChunkData(
            section=SectionType.ITEM_7,
            section_title="MD&A",
            content_type=ContentType.TEXT,
            content_raw="Apple reported record iPhone sales of $200 billion.",
            content_context=(
                "[Apple | 10-K FY2024 | MD&A]\n\n"
                "Apple reported record iPhone sales of $200 billion."
            ),
            chunk_index=0,
            metadata={"company": "Apple"},
        ),
        ChunkData(
            section=SectionType.ITEM_1A,
            section_title="Risk Factors",
            content_type=ContentType.TEXT,
            content_raw="Climate change may increase operational costs significantly.",
            content_context=(
                "[Apple | 10-K FY2024 | Risk Factors]\n\n"
                "Climate change may increase operational costs significantly."
            ),
            chunk_index=1,
            metadata={"company": "Apple"},
        ),
    ]

    async with db_session() as session:
        doc = Document(
            id=doc_id,
            company_name="Apple",
            cik="0000320193",
            ticker="AAPL",
            filing_type="10-K",
            filing_date=date(2024, 11, 1),
            fiscal_year=2024,
            accession_no=f"test-sim-{uuid.uuid4().hex[:8]}",
            source_url="https://example.com/aapl",
        )
        session.add(doc)
        await session.flush()

        await service.embed_and_store(chunks, doc_id, session)
        await session.commit()

        # Query about iPhone sales — should match chunk 0
        query = "How much revenue did iPhone generate?"
        query_embedding = service.embed_texts([query])[0]

        repo = ChunkRepository(session)
        results = await repo.search_by_cosine_similarity(
            embedding=query_embedding,
            top_k=2,
            document_id=doc_id,
        )

        assert len(results) == 2
        top_chunk, top_score = results[0]
        assert "iPhone" in top_chunk.content_raw
        assert top_score > 0.0

        # The iPhone chunk should rank higher than the climate chunk
        second_chunk, second_score = results[1]
        assert top_score >= second_score

        # Cleanup
        await repo.delete_by_document_id(doc_id)
        from sqlalchemy import text

        await session.execute(text("DELETE FROM documents WHERE id = :id"), {"id": doc_id})
        await session.commit()
