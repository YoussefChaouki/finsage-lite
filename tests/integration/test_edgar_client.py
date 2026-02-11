"""
Integration test for SEC EDGAR client.

Makes real HTTP calls to the SEC EDGAR API.
Run with: pytest tests/integration/test_edgar_client.py -v
"""

import pytest

from src.clients.edgar import EdgarClient


@pytest.mark.integration
@pytest.mark.asyncio(loop_scope="function")
async def test_resolve_and_download_aapl_10k() -> None:
    """
    End-to-end: resolve AAPL ticker → list 10-K filings → verify metadata.

    This test makes real HTTP calls to data.sec.gov.
    """
    async with EdgarClient() as edgar:
        # Step 1: Resolve ticker → CIK
        cik = await edgar.resolve_cik("AAPL")
        assert cik == "0000320193"

        # Step 2: List 10-K filings
        filings = await edgar.get_10k_filings(cik, count=1)
        assert len(filings) >= 1

        filing = filings[0]
        assert filing.company_name  # non-empty
        assert filing.cik == "0000320193"
        assert filing.primary_document.endswith(".htm")
        assert filing.fiscal_year >= 2020
