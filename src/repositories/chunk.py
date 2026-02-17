"""
Chunk Repository

Database access layer for chunk storage and vector similarity search.
All SQL operations go through this repository — never in services or routers.
"""

import logging
import uuid

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.chunk import Chunk

logger = logging.getLogger(__name__)


class ChunkRepository:
    """Repository for Chunk CRUD and vector similarity queries.

    Args:
        session: Async SQLAlchemy session (injected per request).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create_many(self, chunks: list[Chunk]) -> list[Chunk]:
        """Bulk-insert chunks into the database.

        Args:
            chunks: List of Chunk ORM instances to persist.

        Returns:
            The same list, now tracked by the session.
        """
        self._session.add_all(chunks)
        await self._session.flush()
        logger.info("Inserted %d chunks", len(chunks))
        return chunks

    async def get_by_document_id(self, document_id: uuid.UUID) -> list[Chunk]:
        """Fetch all chunks belonging to a document.

        Args:
            document_id: UUID of the parent document.

        Returns:
            List of Chunk objects ordered by chunk_index.
        """
        stmt = select(Chunk).where(Chunk.document_id == document_id).order_by(Chunk.chunk_index)
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def search_by_cosine_similarity(
        self,
        embedding: list[float],
        top_k: int = 5,
        document_id: uuid.UUID | None = None,
    ) -> list[tuple[Chunk, float]]:
        """Find the most similar chunks using cosine distance.

        Uses pgvector's <=> operator (cosine distance).
        Similarity = 1 - distance.

        Args:
            embedding: Query embedding vector (384-dim).
            top_k: Number of results to return.
            document_id: Optional filter to restrict search to a document.

        Returns:
            List of (Chunk, similarity_score) tuples, highest similarity first.
        """
        embedding_literal = f"[{','.join(str(v) for v in embedding)}]"

        params: dict[str, object] = {
            "embedding": embedding_literal,
            "top_k": top_k,
        }

        if document_id is not None:
            query = text("""
                SELECT id, (1 - (embedding <=> :embedding)) AS similarity
                FROM chunks
                WHERE embedding IS NOT NULL AND document_id = :doc_id
                ORDER BY embedding <=> :embedding
                LIMIT :top_k
            """)
            params["doc_id"] = str(document_id)
        else:
            query = text("""
                SELECT id, (1 - (embedding <=> :embedding)) AS similarity
                FROM chunks
                WHERE embedding IS NOT NULL
                ORDER BY embedding <=> :embedding
                LIMIT :top_k
            """)

        result = await self._session.execute(query, params)
        rows = result.fetchall()

        if not rows:
            return []

        # Fetch full Chunk objects for the returned IDs
        chunk_ids = [row[0] for row in rows]
        similarity_map = {row[0]: row[1] for row in rows}

        stmt = select(Chunk).where(Chunk.id.in_(chunk_ids))
        chunk_result = await self._session.execute(stmt)
        chunks_by_id = {c.id: c for c in chunk_result.scalars().all()}

        return [
            (chunks_by_id[cid], similarity_map[cid]) for cid in chunk_ids if cid in chunks_by_id
        ]

    async def delete_by_document_id(self, document_id: uuid.UUID) -> int:
        """Delete all chunks for a document.

        Args:
            document_id: UUID of the parent document.

        Returns:
            Number of rows deleted.
        """
        from sqlalchemy import delete as sa_delete

        stmt = sa_delete(Chunk).where(Chunk.document_id == document_id)
        cursor = await self._session.execute(stmt)
        count = int(cursor.rowcount)  # type: ignore[attr-defined]
        logger.info("Deleted %d chunks for document %s", count, document_id)
        return count
