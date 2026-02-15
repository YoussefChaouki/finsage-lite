"""
Ingestion Service Unit Tests

Tests the IngestionService pipeline with mocked dependencies.
No real EDGAR calls, no real DB, no real embedding model.
"""

import uuid
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from src.clients.edgar import FilingNotFoundError, TickerNotFoundError
from src.models.chunk import Chunk, ContentType, SectionType
from src.models.document import Document
from src.schemas.chunking import ChunkData
from src.schemas.edgar import FilingInfo
from src.schemas.parsing import FilingMetadata, ParsedFiling, SectionContent
from src.services.ingestion import (
    DuplicateDocumentError,
    IngestionError,
    IngestionService,
)

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


def _make_filing_info() -> FilingInfo:
    """Create a sample FilingInfo for testing."""
    return FilingInfo(
        accession_number="0000320193-24-000081",
        filing_date=date(2024, 11, 1),
        primary_document="aapl-20240928.htm",
        company_name="Apple Inc.",
        cik="0000320193",
        fiscal_year=2024,
    )


def _make_parsed_filing() -> ParsedFiling:
    """Create a sample ParsedFiling for testing."""
    return ParsedFiling(
        metadata=FilingMetadata(
            company_name="Apple Inc.",
            cik="0000320193",
            fiscal_year=2024,
            filing_period="FY",
            doc_title="Apple 10-K",
        ),
        sections={
            SectionType.ITEM_1: SectionContent(
                section_type=SectionType.ITEM_1,
                title="Business",
                html_content="<p>Apple designs...</p>",
                text_content="Apple designs and manufactures consumer electronics.",
            ),
            SectionType.ITEM_1A: SectionContent(
                section_type=SectionType.ITEM_1A,
                title="Risk Factors",
                html_content="<p>Risks include...</p>",
                text_content="The company faces various risks including market competition.",
            ),
        },
        all_sections_found=["Item 1: Business", "Item 1A: Risk Factors"],
    )


def _make_chunk_data_list() -> list[ChunkData]:
    """Create sample ChunkData list."""
    return [
        ChunkData(
            section=SectionType.ITEM_1,
            section_title="Business",
            content_type=ContentType.TEXT,
            content_raw="Apple designs and manufactures consumer electronics.",
            content_context="[Apple Inc. | 10-K FY2024 | Business]\n\nApple designs...",
            chunk_index=0,
            metadata={"company": "Apple Inc.", "section": "ITEM_1"},
        ),
        ChunkData(
            section=SectionType.ITEM_1A,
            section_title="Risk Factors",
            content_type=ContentType.TEXT,
            content_raw="The company faces various risks.",
            content_context="[Apple Inc. | 10-K FY2024 | Risk Factors]\n\nThe company...",
            chunk_index=1,
            metadata={"company": "Apple Inc.", "section": "ITEM_1A"},
        ),
    ]


def _make_chunk_models(document_id: uuid.UUID) -> list[Chunk]:
    """Create sample Chunk ORM instances."""
    return [
        Chunk(
            id=uuid.uuid4(),
            document_id=document_id,
            section=SectionType.ITEM_1,
            section_title="Business",
            content_type=ContentType.TEXT,
            content_raw="Apple designs...",
            content_context="[Apple Inc. | 10-K FY2024 | Business]\n\nApple...",
            embedding=[0.1] * 384,
            chunk_index=0,
            metadata_={"company": "Apple Inc."},
        ),
    ]


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


class TestIngestionService:
    """Tests for IngestionService.ingest()."""

    @pytest.fixture()
    def mock_session(self) -> AsyncMock:
        """Mock async DB session."""
        session = AsyncMock()
        session.commit = AsyncMock()
        session.flush = AsyncMock()
        session.add = MagicMock()
        return session

    @pytest.fixture()
    def mock_embedding_service(self) -> MagicMock:
        """Mock EmbeddingService."""
        svc = MagicMock()
        svc.embed_and_store = AsyncMock(return_value=[])
        return svc

    @pytest.fixture()
    def service(self, mock_embedding_service: MagicMock) -> IngestionService:
        """Create an IngestionService with mocked embedding service."""
        return IngestionService(embedding_service=mock_embedding_service)

    @pytest.mark.asyncio(loop_scope="session")
    async def test_ingest_success(
        self,
        service: IngestionService,
        mock_session: AsyncMock,
        mock_embedding_service: MagicMock,
    ) -> None:
        """Full pipeline completes successfully with all mocked dependencies."""
        filing = _make_filing_info()
        parsed = _make_parsed_filing()
        chunks = _make_chunk_data_list()

        with (
            patch("src.services.ingestion.DocumentRepository") as MockDocRepo,
            patch("src.services.ingestion.EdgarClient") as MockEdgar,
            patch.object(service, "_parser") as mock_parser,
            patch.object(service, "_chunker") as mock_chunker,
        ):
            # Setup document repository mock
            repo_instance = MockDocRepo.return_value
            repo_instance.get_by_ticker_and_year = AsyncMock(return_value=None)
            repo_instance.create = AsyncMock(side_effect=lambda doc: doc)
            repo_instance.update_processed = AsyncMock()

            # Setup EDGAR client mock (async context manager)
            edgar_instance = AsyncMock()
            edgar_instance.resolve_cik = AsyncMock(return_value="0000320193")
            edgar_instance.get_10k_filings = AsyncMock(return_value=[filing])
            edgar_instance.download_filing = AsyncMock(return_value=Path("/tmp/test_filing.html"))
            MockEdgar.return_value.__aenter__ = AsyncMock(return_value=edgar_instance)
            MockEdgar.return_value.__aexit__ = AsyncMock(return_value=False)

            # Setup parser and chunker mocks
            mock_parser.parse_html.return_value = parsed
            mock_chunker.chunk_section.side_effect = [
                [chunks[0]],  # ITEM_1
                [chunks[1]],  # ITEM_1A
            ]

            result = await service.ingest("AAPL", 2024, mock_session)

            assert result.ticker == "AAPL"
            assert result.fiscal_year == 2024
            assert result.processed is True
            assert result.company_name == "Apple Inc."

            # Verify pipeline steps were called
            repo_instance.get_by_ticker_and_year.assert_called_once_with("AAPL", 2024)
            repo_instance.create.assert_called_once()
            mock_parser.parse_html.assert_called_once()
            assert mock_chunker.chunk_section.call_count == 2
            mock_embedding_service.embed_and_store.assert_called_once()
            repo_instance.update_processed.assert_called_once()
            mock_session.commit.assert_called_once()

    @pytest.mark.asyncio(loop_scope="session")
    async def test_ingest_duplicate_raises(
        self,
        service: IngestionService,
        mock_session: AsyncMock,
    ) -> None:
        """Raises DuplicateDocumentError if document already exists."""
        existing_doc = Document(
            id=uuid.uuid4(),
            company_name="Apple Inc.",
            cik="0000320193",
            ticker="AAPL",
            filing_type="10-K",
            filing_date=date(2024, 11, 1),
            fiscal_year=2024,
            accession_no="0000320193-24-000081",
            source_url="https://sec.gov/...",
            processed=True,
        )

        with patch("src.services.ingestion.DocumentRepository") as MockDocRepo:
            repo_instance = MockDocRepo.return_value
            repo_instance.get_by_ticker_and_year = AsyncMock(return_value=existing_doc)

            with pytest.raises(DuplicateDocumentError) as exc_info:
                await service.ingest("AAPL", 2024, mock_session)

            assert exc_info.value.document is existing_doc

    @pytest.mark.asyncio(loop_scope="session")
    async def test_ingest_ticker_not_found(
        self,
        service: IngestionService,
        mock_session: AsyncMock,
    ) -> None:
        """Raises TickerNotFoundError when ticker cannot be resolved."""
        with (
            patch("src.services.ingestion.DocumentRepository") as MockDocRepo,
            patch("src.services.ingestion.EdgarClient") as MockEdgar,
        ):
            repo_instance = MockDocRepo.return_value
            repo_instance.get_by_ticker_and_year = AsyncMock(return_value=None)

            edgar_instance = AsyncMock()
            edgar_instance.resolve_cik = AsyncMock(
                side_effect=TickerNotFoundError("Ticker 'FAKE' not found")
            )
            MockEdgar.return_value.__aenter__ = AsyncMock(return_value=edgar_instance)
            MockEdgar.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(TickerNotFoundError):
                await service.ingest("FAKE", 2024, mock_session)

    @pytest.mark.asyncio(loop_scope="session")
    async def test_ingest_filing_year_not_found(
        self,
        service: IngestionService,
        mock_session: AsyncMock,
    ) -> None:
        """Raises FilingNotFoundError when fiscal year has no matching 10-K."""
        filing_2023 = FilingInfo(
            accession_number="0000320193-23-000081",
            filing_date=date(2023, 11, 1),
            primary_document="aapl-20230930.htm",
            company_name="Apple Inc.",
            cik="0000320193",
            fiscal_year=2023,
        )

        with (
            patch("src.services.ingestion.DocumentRepository") as MockDocRepo,
            patch("src.services.ingestion.EdgarClient") as MockEdgar,
        ):
            repo_instance = MockDocRepo.return_value
            repo_instance.get_by_ticker_and_year = AsyncMock(return_value=None)

            edgar_instance = AsyncMock()
            edgar_instance.resolve_cik = AsyncMock(return_value="0000320193")
            edgar_instance.get_10k_filings = AsyncMock(return_value=[filing_2023])
            MockEdgar.return_value.__aenter__ = AsyncMock(return_value=edgar_instance)
            MockEdgar.return_value.__aexit__ = AsyncMock(return_value=False)

            with pytest.raises(FilingNotFoundError, match="Available years"):
                await service.ingest("AAPL", 2025, mock_session)

    @pytest.mark.asyncio(loop_scope="session")
    async def test_ingest_parsing_failure(
        self,
        service: IngestionService,
        mock_session: AsyncMock,
    ) -> None:
        """Raises IngestionError when HTML parsing fails."""
        filing = _make_filing_info()

        with (
            patch("src.services.ingestion.DocumentRepository") as MockDocRepo,
            patch("src.services.ingestion.EdgarClient") as MockEdgar,
            patch.object(service, "_parser") as mock_parser,
        ):
            repo_instance = MockDocRepo.return_value
            repo_instance.get_by_ticker_and_year = AsyncMock(return_value=None)

            edgar_instance = AsyncMock()
            edgar_instance.resolve_cik = AsyncMock(return_value="0000320193")
            edgar_instance.get_10k_filings = AsyncMock(return_value=[filing])
            edgar_instance.download_filing = AsyncMock(return_value=Path("/tmp/test.html"))
            MockEdgar.return_value.__aenter__ = AsyncMock(return_value=edgar_instance)
            MockEdgar.return_value.__aexit__ = AsyncMock(return_value=False)

            from src.services.parsing import ParsingError

            mock_parser.parse_html.side_effect = ParsingError("No sections found")

            with pytest.raises(IngestionError, match="Failed to parse"):
                await service.ingest("AAPL", 2024, mock_session)

    @pytest.mark.asyncio(loop_scope="session")
    async def test_ingest_no_chunks_produced(
        self,
        service: IngestionService,
        mock_session: AsyncMock,
    ) -> None:
        """Raises IngestionError when chunking produces zero chunks."""
        filing = _make_filing_info()
        parsed = _make_parsed_filing()

        with (
            patch("src.services.ingestion.DocumentRepository") as MockDocRepo,
            patch("src.services.ingestion.EdgarClient") as MockEdgar,
            patch.object(service, "_parser") as mock_parser,
            patch.object(service, "_chunker") as mock_chunker,
        ):
            repo_instance = MockDocRepo.return_value
            repo_instance.get_by_ticker_and_year = AsyncMock(return_value=None)
            repo_instance.create = AsyncMock(side_effect=lambda doc: doc)

            edgar_instance = AsyncMock()
            edgar_instance.resolve_cik = AsyncMock(return_value="0000320193")
            edgar_instance.get_10k_filings = AsyncMock(return_value=[filing])
            edgar_instance.download_filing = AsyncMock(return_value=Path("/tmp/test.html"))
            MockEdgar.return_value.__aenter__ = AsyncMock(return_value=edgar_instance)
            MockEdgar.return_value.__aexit__ = AsyncMock(return_value=False)

            mock_parser.parse_html.return_value = parsed
            mock_chunker.chunk_section.return_value = []  # No chunks

            with pytest.raises(IngestionError, match="No chunks produced"):
                await service.ingest("AAPL", 2024, mock_session)


class TestDocumentRouter:
    """Tests for document router endpoints using FastAPI TestClient."""

    @pytest.mark.asyncio(loop_scope="session")
    async def test_ingest_request_validation(self) -> None:
        """IngestRequest validates ticker and fiscal_year fields."""
        from src.schemas.document import IngestRequest

        req = IngestRequest(ticker="AAPL", fiscal_year=2024)
        assert req.ticker == "AAPL"
        assert req.fiscal_year == 2024

    @pytest.mark.asyncio(loop_scope="session")
    async def test_ingest_request_rejects_empty_ticker(self) -> None:
        """IngestRequest rejects empty ticker."""
        from pydantic import ValidationError

        from src.schemas.document import IngestRequest

        with pytest.raises(ValidationError):
            IngestRequest(ticker="", fiscal_year=2024)

    @pytest.mark.asyncio(loop_scope="session")
    async def test_ingest_request_rejects_invalid_year(self) -> None:
        """IngestRequest rejects fiscal year out of range."""
        from pydantic import ValidationError

        from src.schemas.document import IngestRequest

        with pytest.raises(ValidationError):
            IngestRequest(ticker="AAPL", fiscal_year=1900)

    @pytest.mark.asyncio(loop_scope="session")
    async def test_document_response_schema(self) -> None:
        """DocumentResponse serializes correctly."""
        from datetime import datetime

        from src.schemas.document import DocumentResponse, SectionSummary

        resp = DocumentResponse(
            id=uuid.uuid4(),
            company_name="Apple Inc.",
            ticker="AAPL",
            cik="0000320193",
            fiscal_year=2024,
            filing_type="10-K",
            filing_date=date(2024, 11, 1),
            accession_no="0000320193-24-000081",
            source_url="https://sec.gov/...",
            processed=True,
            created_at=datetime.utcnow(),
            num_chunks=100,
            sections=[
                SectionSummary(
                    section="ITEM_1A",
                    section_title="Risk Factors",
                    num_chunks=50,
                ),
            ],
        )
        data = resp.model_dump()
        assert data["num_chunks"] == 100
        assert len(data["sections"]) == 1
        assert data["sections"][0]["section"] == "ITEM_1A"
