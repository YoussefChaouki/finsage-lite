"""
Parsing Schemas

Pydantic schemas for HTML filing parsing output.
"""

from pydantic import BaseModel, Field

from src.models.chunk import SectionType


class FilingMetadata(BaseModel):
    """Metadata extracted from a parsed 10-K filing.

    Attributes:
        company_name: Entity registrant name from iXBRL metadata.
        cik: Central Index Key (zero-padded) from iXBRL metadata.
        fiscal_year: Fiscal year focus from iXBRL metadata (e.g. 2025).
        filing_period: Fiscal period focus (e.g. "FY").
        doc_title: Title from HTML <title> tag (e.g. "aapl-20250927").
    """

    company_name: str = ""
    cik: str = ""
    fiscal_year: int = 0
    filing_period: str = ""
    doc_title: str = ""


class SectionContent(BaseModel):
    """Content of a single extracted section.

    Attributes:
        section_type: The SectionType enum value.
        title: Full section title as extracted.
        html_content: Raw HTML of the section (for downstream table parsing).
        text_content: Cleaned plain text (no HTML residual).
    """

    section_type: SectionType
    title: str
    html_content: str
    text_content: str


class ParsedFiling(BaseModel):
    """Result of parsing a 10-K HTML filing.

    Attributes:
        metadata: Filing metadata extracted from iXBRL headers.
        sections: Mapping of SectionType to extracted SectionContent.
        all_sections_found: All Item headings detected (including non-target).
    """

    metadata: FilingMetadata
    sections: dict[SectionType, SectionContent] = Field(default_factory=dict)
    all_sections_found: list[str] = Field(default_factory=list)
