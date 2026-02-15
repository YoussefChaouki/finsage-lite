"""
Document Router

Endpoints for document ingestion, listing, and detail retrieval.
"""

import logging
import uuid

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.edgar import FilingNotFoundError, TickerNotFoundError
from src.core.database import get_db
from src.models.document import Document
from src.repositories.document import DocumentRepository
from src.schemas.document import (
    DocumentListResponse,
    DocumentResponse,
    IngestRequest,
    IngestResponse,
    SectionSummary,
)
from src.services.embedding import EmbeddingService
from src.services.ingestion import (
    DuplicateDocumentError,
    IngestionError,
    IngestionService,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/documents")

# Module-level singleton — model loaded once, reused across requests
_embedding_service: EmbeddingService | None = None


def _get_embedding_service() -> EmbeddingService:
    """Lazy-init singleton for the embedding service."""
    global _embedding_service  # noqa: PLW0603
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service


def _build_document_response(doc: Document) -> DocumentResponse:
    """Build a DocumentResponse from a Document with eagerly loaded chunks.

    Args:
        doc: Document ORM instance with chunks loaded.

    Returns:
        DocumentResponse with section breakdown.
    """
    section_counts = DocumentRepository.get_section_counts(doc)

    # Build section summaries from chunk metadata
    section_titles: dict[str, str] = {}
    for chunk in doc.chunks:
        section_val = chunk.section.value
        if section_val not in section_titles:
            section_titles[section_val] = chunk.section_title or section_val

    sections = [
        SectionSummary(
            section=section,
            section_title=section_titles.get(section, section),
            num_chunks=count,
        )
        for section, count in section_counts.items()
    ]

    return DocumentResponse(
        id=doc.id,
        company_name=doc.company_name,
        ticker=doc.ticker,
        cik=doc.cik,
        fiscal_year=doc.fiscal_year,
        filing_type=doc.filing_type,
        filing_date=doc.filing_date,
        accession_no=doc.accession_no,
        source_url=doc.source_url,
        processed=doc.processed,
        created_at=doc.created_at,
        num_chunks=len(doc.chunks),
        sections=sections,
    )


@router.post("/ingest", response_model=IngestResponse)
async def ingest_document(
    request: IngestRequest,
    session: AsyncSession = Depends(get_db),
) -> IngestResponse:
    """Ingest a SEC 10-K filing.

    Runs the full pipeline: EDGAR → download → parse → chunk → embed → store.

    Args:
        request: Ticker and fiscal year to ingest.
        session: Database session (injected).

    Returns:
        IngestResponse with document ID and status.
    """
    embedding_svc = _get_embedding_service()
    ingestion_svc = IngestionService(embedding_service=embedding_svc)

    try:
        document = await ingestion_svc.ingest(
            ticker=request.ticker,
            fiscal_year=request.fiscal_year,
            session=session,
        )
        return IngestResponse(
            document_id=document.id,
            status="created",
            message=(
                f"Successfully ingested {request.ticker.upper()} FY{request.fiscal_year} "
                f"({len(document.chunks)} chunks)"
            ),
        )
    except DuplicateDocumentError as exc:
        return IngestResponse(
            document_id=exc.document.id,
            status="already_exists",
            message=str(exc),
        )
    except TickerNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except FilingNotFoundError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except IngestionError as exc:
        logger.error("Ingestion failed: %s", exc, exc_info=True)
        raise HTTPException(status_code=500, detail=str(exc)) from exc


@router.get("", response_model=DocumentListResponse)
async def list_documents(
    session: AsyncSession = Depends(get_db),
) -> DocumentListResponse:
    """List all ingested documents.

    Args:
        session: Database session (injected).

    Returns:
        DocumentListResponse with all documents and total count.
    """
    repo = DocumentRepository(session)
    documents = await repo.get_all()

    return DocumentListResponse(
        documents=[_build_document_response(doc) for doc in documents],
        total=len(documents),
    )


@router.get("/{document_id}", response_model=DocumentResponse)
async def get_document(
    document_id: uuid.UUID,
    session: AsyncSession = Depends(get_db),
) -> DocumentResponse:
    """Get details for a specific document.

    Args:
        document_id: UUID of the document.
        session: Database session (injected).

    Returns:
        DocumentResponse with section breakdown and chunk count.
    """
    repo = DocumentRepository(session)
    document = await repo.get_by_id(document_id)

    if document is None:
        raise HTTPException(status_code=404, detail=f"Document {document_id} not found")

    return _build_document_response(document)
