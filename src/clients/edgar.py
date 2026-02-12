"""
SEC EDGAR API Client

Async client for the SEC EDGAR API with rate limiting, caching, and retry logic.
Resolves ticker → CIK, lists 10-K filings, and downloads primary HTML documents.
"""

import asyncio
import logging
from datetime import date, datetime
from pathlib import Path

import httpx

from src.core.config import settings
from src.schemas.edgar import FilingInfo

logger = logging.getLogger(__name__)

# SEC EDGAR base URLs
_SUBMISSIONS_BASE = "https://data.sec.gov/submissions"
_ARCHIVES_BASE = "https://www.sec.gov/Archives/edgar/data"

# Default local cache directory
_DEFAULT_CACHE_DIR = Path("data/filings")

# Retry configuration
_MAX_RETRIES = 3
_RETRY_BACKOFF_BASE = 1.0  # seconds


class EdgarClientError(Exception):
    """Base exception for EDGAR client errors."""


class TickerNotFoundError(EdgarClientError):
    """Raised when a ticker cannot be resolved to a CIK."""


class FilingNotFoundError(EdgarClientError):
    """Raised when no matching filings are found."""


class EdgarClient:
    """
    Async SEC EDGAR API client.

    Features:
        - Ticker → CIK resolution via submissions endpoint
        - 10-K filing listing with metadata
        - HTML filing download with local cache
        - Rate limiting (10 req/s via asyncio.Semaphore)
        - Retry with exponential backoff on transient errors
        - Configurable User-Agent header

    Args:
        user_agent: User-Agent header value (required by SEC).
        cache_dir: Local directory for caching downloaded filings.
        max_concurrent: Maximum concurrent requests (SEC limit: 10/s).
        client: Optional pre-configured httpx.AsyncClient for testing.
    """

    def __init__(
        self,
        user_agent: str = settings.EDGAR_USER_AGENT,
        cache_dir: Path = _DEFAULT_CACHE_DIR,
        max_concurrent: int = 10,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._user_agent = user_agent
        self._cache_dir = cache_dir
        self._semaphore = asyncio.Semaphore(max_concurrent)
        self._external_client = client is not None
        self._client = client or httpx.AsyncClient(
            headers={
                "User-Agent": self._user_agent,
                "Accept": "application/json",
            },
            timeout=httpx.Timeout(30.0),
            follow_redirects=True,
        )

    async def close(self) -> None:
        """Close the underlying HTTP client (only if internally created)."""
        if not self._external_client:
            await self._client.aclose()

    async def __aenter__(self) -> "EdgarClient":
        return self

    async def __aexit__(
        self,
        exc_type: type[BaseException] | None,
        exc_val: BaseException | None,
        exc_tb: object,
    ) -> None:
        await self.close()

    async def _request_with_retry(self, url: str) -> httpx.Response:
        """
        Make a GET request with rate limiting and exponential backoff retry.

        Args:
            url: The URL to request.

        Returns:
            httpx.Response on success.

        Raises:
            EdgarClientError: After all retries are exhausted.
        """
        last_exception: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            async with self._semaphore:
                try:
                    response = await self._client.get(url)

                    if response.status_code == 200:
                        return response

                    if response.status_code == 404:
                        raise EdgarClientError(f"Resource not found: {url}")

                    if response.status_code == 429:
                        wait = _RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                        logger.warning(
                            "Rate limited by SEC EDGAR (attempt %d/%d), retrying in %.1fs",
                            attempt,
                            _MAX_RETRIES,
                            wait,
                        )
                        await asyncio.sleep(wait)
                        continue

                    # Other server errors — retry
                    if response.status_code >= 500:
                        wait = _RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                        logger.warning(
                            "Server error %d from SEC EDGAR (attempt %d/%d), retrying in %.1fs",
                            response.status_code,
                            attempt,
                            _MAX_RETRIES,
                            wait,
                        )
                        await asyncio.sleep(wait)
                        continue

                    raise EdgarClientError(f"Unexpected HTTP {response.status_code} from {url}")

                except httpx.TimeoutException as exc:
                    last_exception = exc
                    wait = _RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                    logger.warning(
                        "Timeout on SEC EDGAR request (attempt %d/%d), retrying in %.1fs",
                        attempt,
                        _MAX_RETRIES,
                        wait,
                    )
                    await asyncio.sleep(wait)

                except httpx.RequestError as exc:
                    last_exception = exc
                    wait = _RETRY_BACKOFF_BASE * (2 ** (attempt - 1))
                    logger.warning(
                        "Request error on SEC EDGAR (attempt %d/%d): %s, retrying in %.1fs",
                        attempt,
                        _MAX_RETRIES,
                        exc,
                        wait,
                    )
                    await asyncio.sleep(wait)

        raise EdgarClientError(
            f"All {_MAX_RETRIES} retries exhausted for {url}"
        ) from last_exception

    async def resolve_cik(self, ticker: str) -> str:
        """
        Resolve a stock ticker symbol to an SEC Central Index Key (CIK).

        Uses the SEC EDGAR submissions endpoint. The CIK is zero-padded
        to 10 digits as required by the API.

        Args:
            ticker: Stock ticker symbol (e.g. "AAPL").

        Returns:
            Zero-padded CIK string (e.g. "0000320193").

        Raises:
            TickerNotFoundError: If the ticker cannot be resolved.
            EdgarClientError: On network or API errors.
        """
        # SEC EDGAR company tickers endpoint
        url = "https://www.sec.gov/files/company_tickers.json"
        response = await self._request_with_retry(url)
        data: dict[str, dict[str, object]] = response.json()

        ticker_upper = ticker.upper()
        for entry in data.values():
            if str(entry.get("ticker", "")).upper() == ticker_upper:
                cik_raw = entry.get("cik_str", entry.get("cik"))
                if cik_raw is not None:
                    return str(cik_raw).zfill(10)

        raise TickerNotFoundError(f"Could not resolve ticker '{ticker}' to CIK")

    async def get_10k_filings(self, cik: str, count: int = 5) -> list[FilingInfo]:
        """
        List the most recent 10-K filings for a given CIK.

        Args:
            cik: Zero-padded CIK string (e.g. "0000320193").
            count: Maximum number of filings to return.

        Returns:
            List of FilingInfo objects sorted by filing date (most recent first).

        Raises:
            FilingNotFoundError: If no 10-K filings are found.
            EdgarClientError: On network or API errors.
        """
        url = f"{_SUBMISSIONS_BASE}/CIK{cik}.json"
        response = await self._request_with_retry(url)
        data: dict[str, object] = response.json()

        company_name = str(data.get("name", "Unknown"))

        recent_filings = data.get("filings", {})
        if isinstance(recent_filings, dict):
            recent = recent_filings.get("recent", {})
        else:
            recent = {}

        forms: list[str] = recent.get("form", [])
        accession_numbers: list[str] = recent.get("accessionNumber", [])
        filing_dates: list[str] = recent.get("filingDate", [])
        primary_docs: list[str] = recent.get("primaryDocument", [])
        report_dates: list[str] = recent.get("reportDate", [])

        filings: list[FilingInfo] = []
        for i, form in enumerate(forms):
            if form != "10-K":
                continue
            if len(filings) >= count:
                break

            # Parse fiscal year from reportDate (period of report)
            fiscal_year = _parse_fiscal_year(
                report_dates[i] if i < len(report_dates) else "",
                filing_dates[i] if i < len(filing_dates) else "",
            )

            filing_date_str = filing_dates[i] if i < len(filing_dates) else ""
            try:
                parsed_date = date.fromisoformat(filing_date_str)
            except ValueError:
                parsed_date = date.today()

            filings.append(
                FilingInfo(
                    accession_number=accession_numbers[i] if i < len(accession_numbers) else "",
                    filing_date=parsed_date,
                    primary_document=primary_docs[i] if i < len(primary_docs) else "",
                    company_name=company_name,
                    cik=cik,
                    fiscal_year=fiscal_year,
                )
            )

        if not filings:
            raise FilingNotFoundError(f"No 10-K filings found for CIK {cik}")

        return filings

    async def download_filing(self, filing: FilingInfo) -> Path:
        """
        Download the primary HTML document for a filing.

        If the file already exists in the local cache, the download is skipped.

        Args:
            filing: FilingInfo with the filing metadata.

        Returns:
            Path to the locally cached HTML file.

        Raises:
            EdgarClientError: On download failure.
        """
        cache_path = filing.local_cache_path(self._cache_dir)

        # Skip download if already cached
        if cache_path.exists():
            logger.info(
                "Filing already cached: %s",
                cache_path,
            )
            return cache_path

        # Ensure cache directory exists
        cache_path.parent.mkdir(parents=True, exist_ok=True)

        url = filing.filing_url
        logger.info("Downloading filing from %s", url)

        response = await self._request_with_retry(url)

        cache_path.write_bytes(response.content)
        logger.info("Filing cached at %s (%d bytes)", cache_path, len(response.content))

        return cache_path


def _parse_fiscal_year(report_date: str, filing_date: str) -> int:
    """
    Extract fiscal year from report date or filing date.

    Args:
        report_date: Period of report date string (YYYY-MM-DD).
        filing_date: Filing date string (YYYY-MM-DD).

    Returns:
        Fiscal year as integer.
    """
    for date_str in (report_date, filing_date):
        if date_str:
            try:
                parsed = datetime.strptime(date_str, "%Y-%m-%d")
                return parsed.year
            except ValueError:
                continue
    return date.today().year
