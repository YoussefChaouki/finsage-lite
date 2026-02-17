"""
Document Model

Represents a SEC 10-K filing in the database.
"""

import uuid
from datetime import UTC, date, datetime

from sqlalchemy import Boolean, Date, Integer, String, Text
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.models.base import Base


class Document(Base):
    """
    SEC 10-K filing document.

    Fields:
        id: Unique identifier
        company_name: Official company name
        cik: Central Index Key (SEC identifier)
        ticker: Stock ticker symbol
        filing_type: Always "10-K"
        filing_date: Date of filing submission
        fiscal_year: Fiscal year end
        accession_no: SEC accession number (unique)
        source_url: Original SEC EDGAR URL
        cached_path: Local file path to cached HTML
        processed: Whether chunking/embedding completed
        created_at: Record creation timestamp
    """

    __tablename__ = "documents"

    id: Mapped[uuid.UUID] = mapped_column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    company_name: Mapped[str] = mapped_column(String(255), nullable=False)
    cik: Mapped[str] = mapped_column(String(10), nullable=False)
    ticker: Mapped[str] = mapped_column(String(10), nullable=False)
    filing_type: Mapped[str] = mapped_column(String(10), nullable=False, default="10-K")
    filing_date: Mapped[date] = mapped_column(Date, nullable=False)
    fiscal_year: Mapped[int] = mapped_column(Integer, nullable=False)
    accession_no: Mapped[str] = mapped_column(String(20), nullable=False, unique=True)
    source_url: Mapped[str] = mapped_column(Text, nullable=False)
    cached_path: Mapped[str] = mapped_column(Text, nullable=True)
    processed: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False)
    created_at: Mapped[datetime] = mapped_column(
        nullable=False, default=lambda: datetime.now(UTC).replace(tzinfo=None)
    )

    # Relationships
    chunks: Mapped[list["Chunk"]] = relationship(  # type: ignore[name-defined]  # noqa: F821
        "Chunk", back_populates="document", cascade="all, delete-orphan"
    )

    def __repr__(self) -> str:
        return f"<Document {self.ticker} FY{self.fiscal_year} id={self.id}>"
