"""
Unit tests for SEC EDGAR client.

All HTTP calls are mocked — no real network requests.
"""

import json
from datetime import date
from pathlib import Path
from unittest.mock import AsyncMock, patch

import httpx
import pytest

from src.clients.edgar import (
    EdgarClient,
    EdgarClientError,
    FilingNotFoundError,
    TickerNotFoundError,
)
from src.schemas.edgar import FilingInfo

# ---------------------------------------------------------------------------
# Fixtures & helpers
# ---------------------------------------------------------------------------

SAMPLE_COMPANY_TICKERS: dict[str, dict[str, object]] = {
    "0": {"cik_str": 320193, "ticker": "AAPL", "title": "Apple Inc."},
    "1": {"cik_str": 789019, "ticker": "MSFT", "title": "Microsoft Corporation"},
}

SAMPLE_SUBMISSIONS: dict[str, object] = {
    "cik": "0000320193",
    "name": "Apple Inc.",
    "filings": {
        "recent": {
            "form": ["10-K", "10-Q", "10-K", "8-K"],
            "accessionNumber": [
                "0000320193-24-000081",
                "0000320193-24-000050",
                "0000320193-23-000077",
                "0000320193-24-000099",
            ],
            "filingDate": ["2024-11-01", "2024-08-01", "2023-11-03", "2024-12-01"],
            "primaryDocument": [
                "aapl-20240928.htm",
                "aapl-20240629.htm",
                "aapl-20230930.htm",
                "aapl-20241201.htm",
            ],
            "reportDate": ["2024-09-28", "2024-06-29", "2023-09-30", "2024-12-01"],
        },
    },
}


def _make_response(
    status_code: int = 200,
    json_data: object = None,
    content: bytes = b"",
) -> httpx.Response:
    """Build a mock httpx.Response."""
    if json_data is not None:
        content = json.dumps(json_data).encode()
    return httpx.Response(
        status_code=status_code,
        content=content,
        request=httpx.Request("GET", "https://example.com"),
        headers={"content-type": "application/json"},
    )


@pytest.fixture()
def mock_client() -> AsyncMock:
    """Pre-configured AsyncMock for httpx.AsyncClient."""
    client = AsyncMock(spec=httpx.AsyncClient)
    client.aclose = AsyncMock()
    return client


# ---------------------------------------------------------------------------
# resolve_cik
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_resolve_cik_success(mock_client: AsyncMock) -> None:
    """resolve_cik returns zero-padded CIK for known ticker."""
    mock_client.get = AsyncMock(return_value=_make_response(json_data=SAMPLE_COMPANY_TICKERS))

    async with EdgarClient(client=mock_client) as edgar:
        cik = await edgar.resolve_cik("AAPL")

    assert cik == "0000320193"


@pytest.mark.asyncio(loop_scope="function")
async def test_resolve_cik_case_insensitive(mock_client: AsyncMock) -> None:
    """resolve_cik is case-insensitive."""
    mock_client.get = AsyncMock(return_value=_make_response(json_data=SAMPLE_COMPANY_TICKERS))

    async with EdgarClient(client=mock_client) as edgar:
        cik = await edgar.resolve_cik("aapl")

    assert cik == "0000320193"


@pytest.mark.asyncio(loop_scope="function")
async def test_resolve_cik_unknown_ticker(mock_client: AsyncMock) -> None:
    """resolve_cik raises TickerNotFoundError for unknown ticker."""
    mock_client.get = AsyncMock(return_value=_make_response(json_data=SAMPLE_COMPANY_TICKERS))

    async with EdgarClient(client=mock_client) as edgar:
        with pytest.raises(TickerNotFoundError, match="INVALID"):
            await edgar.resolve_cik("INVALID")


# ---------------------------------------------------------------------------
# get_10k_filings
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_get_10k_filings_returns_correct_count(mock_client: AsyncMock) -> None:
    """get_10k_filings returns only 10-K filings up to requested count."""
    mock_client.get = AsyncMock(return_value=_make_response(json_data=SAMPLE_SUBMISSIONS))

    async with EdgarClient(client=mock_client) as edgar:
        filings = await edgar.get_10k_filings("0000320193", count=5)

    # Sample data has 2 10-K filings
    assert len(filings) == 2
    assert all(f.form_type == "10-K" for f in filings)


@pytest.mark.asyncio(loop_scope="function")
async def test_get_10k_filings_metadata(mock_client: AsyncMock) -> None:
    """get_10k_filings returns correct metadata for each filing."""
    mock_client.get = AsyncMock(return_value=_make_response(json_data=SAMPLE_SUBMISSIONS))

    async with EdgarClient(client=mock_client) as edgar:
        filings = await edgar.get_10k_filings("0000320193")

    first = filings[0]
    assert first.accession_number == "0000320193-24-000081"
    assert first.filing_date == date(2024, 11, 1)
    assert first.primary_document == "aapl-20240928.htm"
    assert first.company_name == "Apple Inc."
    assert first.cik == "0000320193"
    assert first.fiscal_year == 2024


@pytest.mark.asyncio(loop_scope="function")
async def test_get_10k_filings_respects_count(mock_client: AsyncMock) -> None:
    """get_10k_filings limits results to count parameter."""
    mock_client.get = AsyncMock(return_value=_make_response(json_data=SAMPLE_SUBMISSIONS))

    async with EdgarClient(client=mock_client) as edgar:
        filings = await edgar.get_10k_filings("0000320193", count=1)

    assert len(filings) == 1


@pytest.mark.asyncio(loop_scope="function")
async def test_get_10k_filings_no_results(mock_client: AsyncMock) -> None:
    """get_10k_filings raises FilingNotFoundError when no 10-K filings exist."""
    empty_submissions: dict[str, object] = {
        "cik": "9999999999",
        "name": "No Filing Corp",
        "filings": {
            "recent": {
                "form": ["8-K", "10-Q"],
                "accessionNumber": ["acc1", "acc2"],
                "filingDate": ["2024-01-01", "2024-02-01"],
                "primaryDocument": ["doc1.htm", "doc2.htm"],
                "reportDate": ["2024-01-01", "2024-02-01"],
            },
        },
    }
    mock_client.get = AsyncMock(return_value=_make_response(json_data=empty_submissions))

    async with EdgarClient(client=mock_client) as edgar:
        with pytest.raises(FilingNotFoundError):
            await edgar.get_10k_filings("9999999999")


# ---------------------------------------------------------------------------
# download_filing
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_download_filing_caches_file(
    mock_client: AsyncMock,
    tmp_path: Path,
) -> None:
    """download_filing saves HTML to the local cache."""
    html_content = b"<html><body>10-K Filing Content</body></html>"
    mock_client.get = AsyncMock(return_value=_make_response(content=html_content))

    filing = FilingInfo(
        accession_number="0000320193-24-000081",
        filing_date=date(2024, 11, 1),
        primary_document="aapl-20240928.htm",
        company_name="Apple Inc.",
        cik="0000320193",
        fiscal_year=2024,
    )

    async with EdgarClient(client=mock_client, cache_dir=tmp_path) as edgar:
        path = await edgar.download_filing(filing)

    assert path.exists()
    assert path.read_bytes() == html_content
    assert path.name == "0000320193_0000320193-24-000081.html"


@pytest.mark.asyncio(loop_scope="function")
async def test_download_filing_skips_if_cached(
    mock_client: AsyncMock,
    tmp_path: Path,
) -> None:
    """download_filing does not re-download if file exists."""
    filing = FilingInfo(
        accession_number="0000320193-24-000081",
        filing_date=date(2024, 11, 1),
        primary_document="aapl-20240928.htm",
        company_name="Apple Inc.",
        cik="0000320193",
        fiscal_year=2024,
    )

    # Pre-create the cached file
    cache_path = filing.local_cache_path(tmp_path)
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_text("existing content")

    async with EdgarClient(client=mock_client, cache_dir=tmp_path) as edgar:
        path = await edgar.download_filing(filing)

    assert path == cache_path
    assert path.read_text() == "existing content"
    # HTTP client should NOT have been called
    mock_client.get.assert_not_called()


# ---------------------------------------------------------------------------
# Retry / error handling
# ---------------------------------------------------------------------------


@pytest.mark.asyncio(loop_scope="function")
async def test_retry_on_timeout(mock_client: AsyncMock) -> None:
    """Client retries on timeout and succeeds on subsequent attempt."""
    mock_client.get = AsyncMock(
        side_effect=[
            httpx.TimeoutException("timeout"),
            _make_response(json_data=SAMPLE_COMPANY_TICKERS),
        ]
    )

    async with EdgarClient(client=mock_client) as edgar:
        with patch("src.clients.edgar.asyncio.sleep", new_callable=AsyncMock):
            cik = await edgar.resolve_cik("AAPL")

    assert cik == "0000320193"
    assert mock_client.get.call_count == 2


@pytest.mark.asyncio(loop_scope="function")
async def test_retry_exhausted_raises(mock_client: AsyncMock) -> None:
    """Client raises EdgarClientError after all retries are exhausted."""
    mock_client.get = AsyncMock(side_effect=httpx.TimeoutException("timeout"))

    async with EdgarClient(client=mock_client) as edgar:
        with (
            patch("src.clients.edgar.asyncio.sleep", new_callable=AsyncMock),
            pytest.raises(EdgarClientError, match="retries exhausted"),
        ):
            await edgar.resolve_cik("AAPL")


@pytest.mark.asyncio(loop_scope="function")
async def test_404_raises_immediately(mock_client: AsyncMock) -> None:
    """Client raises EdgarClientError on 404 without retry."""
    mock_client.get = AsyncMock(return_value=_make_response(status_code=404))

    async with EdgarClient(client=mock_client) as edgar:
        with pytest.raises(EdgarClientError, match="not found"):
            await edgar.resolve_cik("AAPL")

    assert mock_client.get.call_count == 1


# ---------------------------------------------------------------------------
# FilingInfo schema
# ---------------------------------------------------------------------------


def test_filing_info_url() -> None:
    """FilingInfo.filing_url constructs the correct EDGAR URL."""
    filing = FilingInfo(
        accession_number="0000320193-24-000081",
        filing_date=date(2024, 11, 1),
        primary_document="aapl-20240928.htm",
        company_name="Apple Inc.",
        cik="0000320193",
        fiscal_year=2024,
    )
    assert filing.filing_url == (
        "https://www.sec.gov/Archives/edgar/data/0000320193/000032019324000081/aapl-20240928.htm"
    )


def test_filing_info_cache_path(tmp_path: Path) -> None:
    """FilingInfo.local_cache_path returns expected path format."""
    filing = FilingInfo(
        accession_number="0000320193-24-000081",
        filing_date=date(2024, 11, 1),
        primary_document="aapl-20240928.htm",
        company_name="Apple Inc.",
        cik="0000320193",
        fiscal_year=2024,
    )
    path = filing.local_cache_path(tmp_path)
    assert path == tmp_path / "0000320193_0000320193-24-000081.html"
