"""
SEC EDGAR Schemas

Pydantic schemas for SEC EDGAR API responses and filing metadata.
"""

from datetime import date
from pathlib import Path

from pydantic import BaseModel


class FilingInfo(BaseModel):
    """
    Metadata for a single SEC filing.

    Attributes:
        accession_number: SEC accession number (e.g. "0000320193-24-000081")
        filing_date: Date the filing was submitted
        primary_document: Filename of the primary HTML document
        company_name: Official company name from SEC
        cik: Central Index Key
        fiscal_year: Fiscal year end (derived from period of report)
        form_type: SEC form type (e.g. "10-K")
    """

    accession_number: str
    filing_date: date
    primary_document: str
    company_name: str
    cik: str
    fiscal_year: int
    form_type: str = "10-K"

    @property
    def accession_no_dashes(self) -> str:
        """Accession number without dashes, used in EDGAR URLs."""
        return self.accession_number.replace("-", "")

    @property
    def filing_url(self) -> str:
        """Full URL to the primary document on SEC EDGAR."""
        return (
            f"https://www.sec.gov/Archives/edgar/data/"
            f"{self.cik}/{self.accession_no_dashes}/{self.primary_document}"
        )

    def local_cache_path(self, base_dir: Path) -> Path:
        """
        Local cache file path for the downloaded filing.

        Args:
            base_dir: Base directory for filing cache (e.g. data/filings/).

        Returns:
            Path in the format {base_dir}/{cik}_{accession_number}.html
        """
        return base_dir / f"{self.cik}_{self.accession_number}.html"
