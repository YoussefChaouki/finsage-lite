"""
Document Schemas

Pydantic schemas for document ingestion request/response and listing endpoints.
"""

import uuid
from datetime import date, datetime

from pydantic import BaseModel, Field


class IngestRequest(BaseModel):
    """Request body for document ingestion.

    Attributes:
        ticker: Stock ticker symbol (e.g. "AAPL").
        fiscal_year: Fiscal year to ingest (e.g. 2024).
    """

    ticker: str = Field(..., min_length=1, max_length=10, examples=["AAPL"])
    fiscal_year: int = Field(..., ge=1993, le=2030, examples=[2024])


class IngestResponse(BaseModel):
    """Response after ingestion completes.

    Attributes:
        document_id: UUID of the created/existing document.
        status: Processing status ("created", "already_exists").
        message: Human-readable status message.
    """

    document_id: uuid.UUID
    status: str
    message: str


class SectionSummary(BaseModel):
    """Summary of a section within a document.

    Attributes:
        section: Section type (e.g. "ITEM_1A").
        section_title: Human-readable title.
        num_chunks: Number of chunks in this section.
    """

    section: str
    section_title: str
    num_chunks: int


class DocumentResponse(BaseModel):
    """Detailed document representation.

    Attributes:
        id: Document UUID.
        company_name: Official company name.
        ticker: Stock ticker symbol.
        cik: SEC Central Index Key.
        fiscal_year: Fiscal year.
        filing_type: SEC form type.
        filing_date: Filing submission date.
        accession_no: SEC accession number.
        source_url: Original SEC EDGAR URL.
        processed: Whether processing is complete.
        created_at: Record creation timestamp.
        num_chunks: Total number of chunks.
        sections: Breakdown by section.
    """

    id: uuid.UUID
    company_name: str
    ticker: str
    cik: str
    fiscal_year: int
    filing_type: str
    filing_date: date
    accession_no: str
    source_url: str
    processed: bool
    created_at: datetime
    num_chunks: int = 0
    sections: list[SectionSummary] = Field(default_factory=list)


class DocumentListResponse(BaseModel):
    """Response for listing documents.

    Attributes:
        documents: List of document summaries.
        total: Total number of documents.
    """

    documents: list[DocumentResponse]
    total: int
