"""
Ingestion Service

Orchestrates the full SEC 10-K ingestion pipeline:
EDGAR → download → parse → chunk → embed → store.
"""

import logging
from pathlib import Path

from sqlalchemy.ext.asyncio import AsyncSession

from src.clients.edgar import (
    EdgarClient,
    EdgarClientError,
    FilingNotFoundError,
    TickerNotFoundError,
)
from src.models.document import Document
from src.repositories.document import DocumentRepository
from src.schemas.chunking import ChunkData
from src.schemas.edgar import FilingInfo
from src.services.chunking import SectionChunker
from src.services.embedding import EmbeddingService
from src.services.parsing import FilingParser, ParsingError

logger = logging.getLogger(__name__)


class IngestionError(Exception):
    """Base exception for ingestion pipeline errors."""


class DuplicateDocumentError(IngestionError):
    """Raised when a document has already been ingested."""

    def __init__(self, document: Document) -> None:
        self.document = document
        super().__init__(
            f"Document already exists: {document.ticker} FY{document.fiscal_year} "
            f"(id={document.id})"
        )


class IngestionService:
    """Orchestrates the full ingestion pipeline for SEC 10-K filings.

    Pipeline steps:
        1. Duplicate check (ticker + fiscal_year)
        2. Resolve ticker → CIK via SEC EDGAR
        3. Fetch 10-K filing list and find matching fiscal year
        4. Download primary HTML document
        5. Parse HTML into sections
        6. Chunk sections into overlapping text segments
        7. Generate embeddings and store chunks in pgvector
        8. Mark document as processed

    Args:
        embedding_service: Pre-initialized EmbeddingService (model loaded once).
    """

    def __init__(self, embedding_service: EmbeddingService) -> None:
        self._embedding_service = embedding_service
        self._parser = FilingParser()
        self._chunker = SectionChunker()

    async def ingest(
        self,
        ticker: str,
        fiscal_year: int,
        session: AsyncSession,
    ) -> tuple[Document, int]:
        """Run the full ingestion pipeline for a single 10-K filing.

        Args:
            ticker: Stock ticker symbol (e.g. "AAPL").
            fiscal_year: Fiscal year to ingest (e.g. 2024).
            session: Async DB session for the transaction.

        Returns:
            Tuple of (Document, chunk_count). The chunk count is returned
            separately to avoid lazy-loading the chunks relationship
            after commit.

        Raises:
            DuplicateDocumentError: If the document was already ingested.
            TickerNotFoundError: If the ticker cannot be resolved.
            FilingNotFoundError: If no 10-K filing matches the fiscal year.
            ParsingError: If the HTML cannot be parsed.
            IngestionError: On any other pipeline failure.
        """
        doc_repo = DocumentRepository(session)

        # 1. Duplicate check
        existing = await doc_repo.get_by_ticker_and_year(ticker, fiscal_year)
        if existing is not None:
            logger.info("Document already exists: %s FY%d", ticker, fiscal_year)
            raise DuplicateDocumentError(existing)

        # 2–4. EDGAR: resolve CIK → list filings → download
        filing, html_path = await self._fetch_and_download(ticker, fiscal_year)

        logger.info("Downloaded filing to %s", html_path)

        # 5. Parse HTML
        try:
            parsed = self._parser.parse_html(html_path)
        except (FileNotFoundError, ParsingError) as exc:
            raise IngestionError(f"Failed to parse filing: {exc}") from exc

        logger.info(
            "Parsed %d sections from %s FY%d",
            len(parsed.sections),
            ticker,
            fiscal_year,
        )

        # 4b. Create Document record
        document = Document(
            company_name=filing.company_name,
            cik=filing.cik,
            ticker=ticker.upper(),
            filing_type=filing.form_type,
            filing_date=filing.filing_date,
            fiscal_year=fiscal_year,
            accession_no=filing.accession_number,
            source_url=filing.filing_url,
            cached_path=str(html_path),
            processed=False,
        )
        await doc_repo.create(document)

        # 6. Chunk all sections
        all_chunks: list[ChunkData] = []
        for section_type, section_content in parsed.sections.items():
            chunks = self._chunker.chunk_section(
                text=section_content.text_content,
                section=section_type,
                section_title=section_content.title,
                company_name=filing.company_name,
                cik=filing.cik,
                fiscal_year=fiscal_year,
            )
            all_chunks.extend(chunks)

        if not all_chunks:
            raise IngestionError(
                f"No chunks produced for {ticker} FY{fiscal_year} — sections may be empty"
            )

        # Re-index chunks sequentially across all sections
        for idx, chunk in enumerate(all_chunks):
            chunk.chunk_index = idx
            chunk.metadata["chunk_index"] = idx
            chunk.metadata["total_chunks"] = len(all_chunks)

        logger.info("Produced %d chunks across %d sections", len(all_chunks), len(parsed.sections))

        # 7. Embed and store
        await self._embedding_service.embed_and_store(all_chunks, document.id, session)

        # 8. Mark processed
        await doc_repo.update_processed(document.id, True)
        document.processed = True

        await session.commit()

        logger.info(
            "Ingestion complete: %s FY%d → %d chunks stored (doc_id=%s)",
            ticker,
            fiscal_year,
            len(all_chunks),
            document.id,
        )
        return document, len(all_chunks)

    async def _fetch_and_download(self, ticker: str, fiscal_year: int) -> tuple[FilingInfo, Path]:
        """Resolve ticker, find the matching 10-K filing, and download it.

        Uses a single EdgarClient instance for the entire EDGAR interaction
        (CIK resolution + filing listing + download).

        Args:
            ticker: Stock ticker symbol.
            fiscal_year: Target fiscal year.

        Returns:
            Tuple of (FilingInfo, local_path) for the downloaded filing.

        Raises:
            TickerNotFoundError: If ticker cannot be resolved.
            FilingNotFoundError: If no 10-K matches the fiscal year.
            IngestionError: On EDGAR API or download errors.
        """

        try:
            async with EdgarClient() as edgar:
                cik = await edgar.resolve_cik(ticker)
                filings = await edgar.get_10k_filings(cik, count=10)

                # Find the filing matching the requested fiscal year
                matched: FilingInfo | None = None
                for filing in filings:
                    if filing.fiscal_year == fiscal_year:
                        matched = filing
                        break

                if matched is None:
                    available_years = sorted({f.fiscal_year for f in filings}, reverse=True)
                    raise FilingNotFoundError(
                        f"No 10-K filing found for {ticker} FY{fiscal_year}. "
                        f"Available years: {available_years}"
                    )

                logger.info(
                    "Found 10-K for %s FY%d: accession=%s",
                    ticker,
                    fiscal_year,
                    matched.accession_number,
                )

                html_path: Path = await edgar.download_filing(matched)
        except (TickerNotFoundError, FilingNotFoundError):
            raise
        except EdgarClientError:
            raise
        except OSError as exc:
            raise IngestionError(f"Failed to download/cache filing: {exc}") from exc

        return matched, html_path
