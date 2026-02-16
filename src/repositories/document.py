"""
Document Repository

Database access layer for document CRUD operations.
All SQL operations go through this repository — never in services or routers.
"""

import logging
import uuid
from collections import Counter

from sqlalchemy import func, select, update
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from src.models.document import Document

logger = logging.getLogger(__name__)


class DocumentRepository:
    """Repository for Document CRUD operations.

    Args:
        session: Async SQLAlchemy session (injected per request).
    """

    def __init__(self, session: AsyncSession) -> None:
        self._session = session

    async def create(self, document: Document) -> Document:
        """Insert a new document.

        Args:
            document: Document ORM instance to persist.

        Returns:
            The persisted Document, tracked by the session.
        """
        self._session.add(document)
        await self._session.flush()
        logger.info(
            "Created document %s (%s FY%d)", document.id, document.ticker, document.fiscal_year
        )
        return document

    async def get_by_id(self, document_id: uuid.UUID) -> Document | None:
        """Fetch a document by ID with its chunks eagerly loaded.

        Args:
            document_id: UUID of the document.

        Returns:
            Document if found, None otherwise.
        """
        stmt = (
            select(Document)
            .where(Document.id == document_id)
            .options(selectinload(Document.chunks))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def get_all(self) -> list[Document]:
        """Fetch all documents ordered by creation date (newest first).

        Returns:
            List of Document objects.
        """
        stmt = (
            select(Document)
            .options(selectinload(Document.chunks))
            .order_by(Document.created_at.desc())
        )
        result = await self._session.execute(stmt)
        return list(result.scalars().all())

    async def get_by_ticker_and_year(self, ticker: str, fiscal_year: int) -> Document | None:
        """Find a document by ticker and fiscal year (duplicate check).

        Args:
            ticker: Stock ticker symbol (case-insensitive).
            fiscal_year: Fiscal year.

        Returns:
            Document if found, None otherwise.
        """
        stmt = (
            select(Document)
            .where(
                func.upper(Document.ticker) == ticker.upper(),
                Document.fiscal_year == fiscal_year,
            )
            .options(selectinload(Document.chunks))
        )
        result = await self._session.execute(stmt)
        return result.scalar_one_or_none()

    async def update_processed(self, document_id: uuid.UUID, processed: bool) -> None:
        """Update the processed flag for a document.

        Args:
            document_id: UUID of the document.
            processed: New processed status.
        """
        stmt = update(Document).where(Document.id == document_id).values(processed=processed)
        await self._session.execute(stmt)
        logger.info("Updated document %s processed=%s", document_id, processed)

    @staticmethod
    def get_section_counts(document: Document) -> Counter[str]:
        """Count chunks per section for a document.

        Args:
            document: Document with chunks eagerly loaded.

        Returns:
            Counter mapping section name to chunk count.
        """
        counter: Counter[str] = Counter()
        for chunk in document.chunks:
            counter[chunk.section.value] += 1
        return counter
