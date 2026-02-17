"""
Chunk Model

Represents a text or table chunk from a document with embeddings.
"""

import enum
import uuid
from datetime import UTC, datetime
from typing import Any

from pgvector.sqlalchemy import Vector
from sqlalchemy import Enum, ForeignKey, Integer, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.core.config import settings
from src.models.base import Base


class SectionType(enum.StrEnum):
    """SEC 10-K section types."""

    ITEM_1 = "ITEM_1"
    ITEM_1A = "ITEM_1A"
    ITEM_7 = "ITEM_7"
    ITEM_7A = "ITEM_7A"
    ITEM_8 = "ITEM_8"
    OTHER = "OTHER"


class ContentType(enum.StrEnum):
    """Content type of the chunk."""

    TEXT = "TEXT"
    TABLE = "TABLE"


class Chunk(Base):
    """
    Text or table chunk from a document with embedding.

    Fields:
        id: Unique identifier
        document_id: Foreign key to Document
        section: SEC 10-K section (ITEM_1, ITEM_1A, etc.)
        section_title: Human-readable section title
        content_type: TEXT or TABLE
        content_raw: Raw text for BM25 / JSON for tables
        content_context: Prefixed text for embedding / description for tables
        embedding: Vector embedding (384-dim)
        chunk_index: Sequential index within document
        metadata: Additional metadata (page_approx, table_title, etc.)
        created_at: Record creation timestamp
    """

    __tablename__ = "chunks"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    document_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True), ForeignKey("documents.id", ondelete="CASCADE"), nullable=False
    )
    section: Mapped[SectionType] = mapped_column(
        Enum(SectionType), nullable=False, default=SectionType.OTHER
    )
    section_title: Mapped[str] = mapped_column(String(255), nullable=True)
    content_type: Mapped[ContentType] = mapped_column(
        Enum(ContentType), nullable=False, default=ContentType.TEXT
    )
    content_raw: Mapped[str] = mapped_column(Text, nullable=False)
    content_context: Mapped[str] = mapped_column(Text, nullable=False)
    embedding: Mapped[Any] = mapped_column(Vector(settings.EMBEDDING_DIMENSION), nullable=False)
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column("metadata", JSONB, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )

    # Relationships
    document: Mapped["Document"] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Document", back_populates="chunks"
    )

    def __repr__(self) -> str:
        return f"<Chunk #{self.chunk_index} {self.section} id={self.id}>"
