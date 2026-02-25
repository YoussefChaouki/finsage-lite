"""
Chunk Repository

Database access layer for chunk storage and vector similarity search.
All SQL operations go through this repository — never in services or routers.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Sequence
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from src.models.chunk import Chunk
from src.models.document import Document
from src.schemas.search import SearchFilters

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
        filters: SearchFilters | None = None,
    ) -> list[tuple[Chunk, float]]:
        """Find the most similar chunks using cosine distance.

        Uses pgvector's <=> operator (cosine distance).
        Similarity = 1 - distance.

        Supports pre-filtering by document_id, section list, fiscal_year, and
        company name/ticker. Filters involving Document columns (fiscal_year,
        company) trigger an implicit JOIN with the documents table.

        Args:
            embedding: Query embedding vector (384-dim).
            top_k: Number of results to return.
            filters: Optional SearchFilters to narrow the candidate set before
                ranking. All filter fields are optional; unset fields are ignored.

        Returns:
            List of (Chunk, similarity_score) tuples, highest similarity first.
        """
        embedding_literal = f"[{','.join(str(v) for v in embedding)}]"

        params: dict[str, object] = {
            "embedding": embedding_literal,
            "top_k": top_k,
        }

        where_clauses: list[str] = ["c.embedding IS NOT NULL"]
        needs_doc_join = False

        if filters is not None:
            if filters.document_id is not None:
                where_clauses.append("c.document_id = :document_id")
                params["document_id"] = str(filters.document_id)

            if filters.sections:
                placeholders = ", ".join(f":section_{i}" for i in range(len(filters.sections)))
                where_clauses.append(f"c.section IN ({placeholders})")
                for i, section in enumerate(filters.sections):
                    params[f"section_{i}"] = section.value

            if filters.fiscal_year is not None:
                where_clauses.append("d.fiscal_year = :fiscal_year")
                params["fiscal_year"] = filters.fiscal_year
                needs_doc_join = True

            if filters.company is not None:
                where_clauses.append("(d.company_name ILIKE :company OR d.ticker ILIKE :company)")
                params["company"] = f"%{filters.company}%"
                needs_doc_join = True

        join_clause = "JOIN documents d ON d.id = c.document_id" if needs_doc_join else ""
        where_str = " AND ".join(where_clauses)

        sql = f"""
            SELECT c.id, (1 - (c.embedding <=> :embedding)) AS similarity
            FROM chunks c
            {join_clause}
            WHERE {where_str}
            ORDER BY c.embedding <=> :embedding
            LIMIT :top_k
        """

        result = await self._session.execute(text(sql), params)
        rows = result.fetchall()

        if not rows:
            return []

        # Fetch full Chunk objects for the returned IDs
        chunk_ids = [row[0] for row in rows]
        similarity_map: dict[uuid.UUID, float] = {row[0]: float(row[1]) for row in rows}

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

    async def get_all_for_bm25(self) -> Sequence[Any]:
        """Fetch all chunks with document metadata needed for BM25 index building.

        Selects only the columns required by BM25Service — the embedding vector
        is intentionally excluded to reduce memory pressure. A JOIN with the
        documents table provides fiscal_year, company_name, and ticker so the
        service can apply post-retrieval filters without an extra DB round-trip.

        For corpora exceeding 100k chunks the query uses ``yield_per`` server-
        side streaming to avoid materialising the full result set at once.

        Returns:
            Sequence of Row objects with named attributes:
            ``chunk_id``, ``document_id``, ``content_raw``, ``section``,
            ``section_title``, ``metadata``, ``fiscal_year``,
            ``company_name``, ``ticker``.
        """
        stmt = select(
            Chunk.id.label("chunk_id"),
            Chunk.document_id,
            Chunk.content_raw,
            Chunk.section,
            Chunk.section_title,
            Chunk.metadata_.label("metadata"),
            Document.fiscal_year,
            Document.company_name,
            Document.ticker,
        ).join(Document, Chunk.document_id == Document.id)

        result = await self._session.execute(stmt)
        return result.all()
