"""
HTML Parser + Section Splitter

Parses SEC 10-K iXBRL HTML filings and splits them into sections.
Handles TOC filtering, page footer removal, and iXBRL tag cleanup.
"""

import logging
import re
import warnings
from pathlib import Path
from typing import NamedTuple

from bs4 import BeautifulSoup, Tag, XMLParsedAsHTMLWarning

from src.core.config import settings
from src.models.chunk import SectionType
from src.schemas.parsing import FilingMetadata, ParsedFiling, SectionContent

logger = logging.getLogger(__name__)

# Mapping from Item number string (lowercase) to SectionType enum
_ITEM_TO_SECTION: dict[str, SectionType] = {
    "1": SectionType.ITEM_1,
    "1a": SectionType.ITEM_1A,
    "7": SectionType.ITEM_7,
    "7a": SectionType.ITEM_7A,
    "8": SectionType.ITEM_8,
}

# Known Item numbers in expected sequential order (for validation)
_ITEM_ORDER: list[str] = [
    "1",
    "1a",
    "1b",
    "1c",
    "2",
    "3",
    "4",
    "5",
    "6",
    "7",
    "7a",
    "8",
    "9",
    "9a",
    "9b",
    "9c",
    "10",
    "11",
    "12",
    "13",
    "14",
    "15",
    "16",
]

# Regex for parsing Item text from a heading span
_ITEM_HEADING_RE = re.compile(
    r"(?i)Item\s+(\d+[A-Za-z]?)[\.\s\xa0\-\u2014:]+(.+)",
)

# Regex for fallback detection on flattened text
_ITEM_TEXT_RE = re.compile(
    r"(?im)^Item\s+(\d+[A-Za-z]?)[\.\s\xa0\-\u2014:]+(.+)$",
)


class _HeadingInfo(NamedTuple):
    """Internal representation of a detected section heading."""

    item_number: str  # e.g. "7a" (lowercase)
    title: str  # e.g. "Quantitative and Qualitative Disclosures About Market Risk"
    element: Tag  # The parent <div> of the bold <span>
    position: int  # Index among body children for ordering


class ParsingError(Exception):
    """Raised when a filing cannot be parsed."""


class FilingParser:
    """Parses SEC 10-K HTML filings and extracts content by section.

    The parser handles iXBRL HTML format commonly produced by SEC EDGAR.
    It identifies section headings via bold <span> elements (font-weight:700),
    filters out Table of Contents entries, extracts iXBRL metadata, and cleans
    page footers and repeated headers.

    Args:
        target_sections: List of Item number strings to extract (e.g. ["1", "1A"]).
            Defaults to settings.PARSING_TARGET_SECTIONS.
    """

    def __init__(self, target_sections: list[str] | None = None) -> None:
        self._target_sections = [
            s.lower() for s in (target_sections or settings.PARSING_TARGET_SECTIONS)
        ]

    def parse_html(self, html_path: Path) -> ParsedFiling:
        """Parse a 10-K HTML filing and split into sections.

        Args:
            html_path: Path to the local HTML filing.

        Returns:
            ParsedFiling with metadata and extracted sections.

        Raises:
            FileNotFoundError: If html_path does not exist.
            ParsingError: If the HTML cannot be parsed or no sections found.
        """
        if not html_path.exists():
            raise FileNotFoundError(f"Filing not found: {html_path}")

        soup = self._load_html(html_path)
        metadata = self._extract_metadata(soup)

        headings = self._find_section_headings(soup)
        if not headings:
            logger.warning("DOM-based detection found no headings, trying text fallback")
            headings = self._find_headings_fallback(soup)

        if not headings:
            raise ParsingError(f"No section headings found in {html_path}")

        self._validate_heading_order(headings)

        all_found = [f"Item {h.item_number.upper()}: {h.title}" for h in headings]
        logger.info("Detected %d section headings in %s", len(headings), html_path.name)

        sections = self._extract_target_sections(headings, metadata)

        return ParsedFiling(
            metadata=metadata,
            sections=sections,
            all_sections_found=all_found,
        )

    def _load_html(self, html_path: Path) -> BeautifulSoup:
        """Load and parse HTML filing with encoding fallback.

        Args:
            html_path: Path to the HTML file.

        Returns:
            Parsed BeautifulSoup object.

        Raises:
            ParsingError: If the file cannot be read or parsed.
        """
        warnings.filterwarnings("ignore", category=XMLParsedAsHTMLWarning)
        try:
            content = html_path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            logger.warning("UTF-8 decode failed for %s, trying latin-1", html_path.name)
            content = html_path.read_text(encoding="latin-1")

        if not content.strip():
            raise ParsingError(f"Empty file: {html_path}")

        return BeautifulSoup(content, "lxml")

    def _extract_metadata(self, soup: BeautifulSoup) -> FilingMetadata:
        """Extract filing metadata from iXBRL dei fields and HTML title.

        Args:
            soup: Parsed HTML document.

        Returns:
            FilingMetadata with extracted fields (defaults if not found).
        """
        dei_fields: dict[str, str] = {}
        for tag in soup.find_all(re.compile(r"^ix:")):
            name = tag.get("name", "")
            if isinstance(name, str) and name.lower().startswith("dei:"):
                field_name = name.split(":")[-1]
                dei_fields[field_name.lower()] = tag.get_text(strip=True)

        company_name = dei_fields.get("entityregistrantname", "")
        cik = dei_fields.get("entitycentralindexkey", "")
        fiscal_year_str = dei_fields.get("documentfiscalyearfocus", "0")
        filing_period = dei_fields.get("documentfiscalperiodfocus", "")
        doc_title = soup.title.get_text(strip=True) if soup.title else ""

        try:
            fiscal_year = int(fiscal_year_str)
        except ValueError:
            fiscal_year = 0

        metadata = FilingMetadata(
            company_name=company_name,
            cik=cik,
            fiscal_year=fiscal_year,
            filing_period=filing_period,
            doc_title=doc_title,
        )
        logger.info(
            "Extracted metadata: company=%s, cik=%s, fy=%d",
            company_name,
            cik,
            fiscal_year,
        )
        return metadata

    def _find_section_headings(self, soup: BeautifulSoup) -> list[_HeadingInfo]:
        """Find section headings via bold spans in the DOM.

        Identifies <span> elements with font-weight:700 whose text matches
        the Item heading pattern. Excludes TOC entries (inside <td> elements).

        Args:
            soup: Parsed HTML document.

        Returns:
            List of _HeadingInfo sorted by document position.
        """
        body = soup.body
        if not body:
            return []

        # Build position index for body children
        body_children = [c for c in body.children if isinstance(c, Tag)]
        child_positions = {id(c): i for i, c in enumerate(body_children)}

        headings: list[_HeadingInfo] = []
        for span in soup.find_all("span", style=re.compile(r"font-weight:\s*700")):
            text = span.get_text(strip=True)
            match = _ITEM_HEADING_RE.match(text)
            if not match:
                continue

            # Skip if inside a table (TOC entry)
            if span.find_parent("table") is not None:
                continue

            parent_div = span.parent
            if not parent_div or not isinstance(parent_div, Tag):
                continue

            # Find the body-level ancestor (direct child of <body>)
            body_div = self._find_body_child(parent_div, body)
            if body_div is None:
                continue

            position = child_positions.get(id(body_div), -1)
            if position < 0:
                continue

            item_num = match.group(1).lower()
            title = match.group(2).strip()

            headings.append(
                _HeadingInfo(
                    item_number=item_num,
                    title=title,
                    element=body_div,
                    position=position,
                )
            )

        headings.sort(key=lambda h: h.position)
        return headings

    def _find_body_child(self, element: Tag, body: Tag) -> Tag | None:
        """Walk up the DOM to find the direct child of <body>.

        Args:
            element: Starting element.
            body: The <body> tag.

        Returns:
            The ancestor that is a direct child of body, or None.
        """
        current = element
        while current and current.parent != body:
            current = current.parent  # type: ignore[assignment]
            if current is None or current.name == "[document]":
                return None
        return current if isinstance(current, Tag) else None

    def _find_headings_fallback(self, soup: BeautifulSoup) -> list[_HeadingInfo]:
        """Fallback: detect headings via regex on flattened text.

        Used when DOM-based detection finds nothing (non-standard HTML structure).

        Args:
            soup: Parsed HTML document.

        Returns:
            List of _HeadingInfo (with position based on text offset).
        """
        body = soup.body
        if not body:
            return []

        text = body.get_text(separator="\n")
        headings: list[_HeadingInfo] = []

        for i, match in enumerate(_ITEM_TEXT_RE.finditer(text)):
            item_num = match.group(1).lower()
            title = match.group(2).strip()
            # Use a dummy Tag — downstream will use text-based extraction
            headings.append(
                _HeadingInfo(
                    item_number=item_num,
                    title=title,
                    element=body,
                    position=i,
                )
            )

        return headings

    def _validate_heading_order(self, headings: list[_HeadingInfo]) -> None:
        """Check that detected headings appear in expected 10-K order.

        Logs a warning for any out-of-order headings but does not reject.

        Args:
            headings: Detected headings sorted by position.
        """
        order_index = {num: i for i, num in enumerate(_ITEM_ORDER)}
        last_idx = -1

        for heading in headings:
            idx = order_index.get(heading.item_number, -1)
            if idx < 0:
                logger.warning("Unknown item number: %s", heading.item_number)
                continue
            if idx < last_idx:
                logger.warning(
                    "Out-of-order heading: Item %s (expected after Item %s)",
                    heading.item_number.upper(),
                    _ITEM_ORDER[last_idx].upper(),
                )
            last_idx = max(last_idx, idx)

    def _extract_target_sections(
        self,
        headings: list[_HeadingInfo],
        metadata: FilingMetadata,
    ) -> dict[SectionType, SectionContent]:
        """Extract content for target sections from detected headings.

        Args:
            headings: All detected headings in order.
            metadata: Filing metadata for cleanup context.

        Returns:
            Dict mapping SectionType to extracted SectionContent.
        """
        target_set = set(self._target_sections)
        sections: dict[SectionType, SectionContent] = {}

        for i, heading in enumerate(headings):
            if heading.item_number not in target_set:
                continue

            section_type = _ITEM_TO_SECTION.get(heading.item_number)
            if section_type is None:
                continue

            next_element = headings[i + 1].element if i + 1 < len(headings) else None
            html_content, text_content = self._extract_section_content(
                heading.element, next_element
            )

            cleaned_text = self._clean_text(
                text_content, metadata.company_name, metadata.fiscal_year
            )

            if not cleaned_text.strip():
                logger.warning(
                    "Empty content for Item %s after cleanup", heading.item_number.upper()
                )
                continue

            sections[section_type] = SectionContent(
                section_type=section_type,
                title=heading.title,
                html_content=html_content,
                text_content=cleaned_text,
            )
            logger.debug(
                "Extracted Item %s: %d chars",
                heading.item_number.upper(),
                len(cleaned_text),
            )

        return sections

    def _extract_section_content(
        self,
        heading_element: Tag,
        next_heading_element: Tag | None,
    ) -> tuple[str, str]:
        """Extract HTML and text content between two heading elements.

        Walks siblings from heading_element (exclusive) to next_heading_element
        (exclusive), collecting both raw HTML and cleaned text.

        Args:
            heading_element: The div containing the section heading.
            next_heading_element: The div of the next section heading, or None.

        Returns:
            Tuple of (html_content, text_content).
        """
        html_parts: list[str] = []
        text_parts: list[str] = []

        sibling = heading_element.next_sibling
        while sibling is not None:
            if isinstance(sibling, Tag):
                if next_heading_element is not None and sibling is next_heading_element:
                    break
                html_parts.append(str(sibling))
                text = sibling.get_text(separator=" ", strip=True)
                if text:
                    text_parts.append(text)
            sibling = sibling.next_sibling

        return "\n".join(html_parts), "\n".join(text_parts)

    def _clean_text(self, text: str, company_name: str, fiscal_year: int) -> str:
        """Apply cleanup pipeline to extracted section text.

        Pipeline:
            1. Remove page footers (Company | Year Form 10-K | N)
            2. Remove "Table of Contents" header lines
            3. Normalize non-breaking spaces
            4. Remove standalone page numbers
            5. Collapse multiple blank lines

        Args:
            text: Raw extracted text.
            company_name: Company name for footer pattern.
            fiscal_year: Fiscal year for footer pattern.

        Returns:
            Cleaned text.
        """
        # 1. Remove page footers
        if company_name and fiscal_year:
            escaped_name = re.escape(company_name)
            footer_pattern = re.compile(
                rf"{escaped_name}\s*\|\s*{fiscal_year}\s+Form\s+10-K\s*\|\s*\d+"
            )
            text = footer_pattern.sub("", text)

        # 2. Remove "Table of Contents" lines
        text = re.sub(r"(?im)^\s*Table\s+of\s+Contents\s*$", "", text)

        # 3. Normalize non-breaking spaces
        text = text.replace("\xa0", " ")

        # 4. Remove standalone page numbers
        text = re.sub(r"(?m)^\s*\d+\s*$", "", text)

        # 5. Collapse multiple blank lines and strip trailing whitespace
        text = re.sub(r"\n{3,}", "\n\n", text)
        text = re.sub(r"[ \t]+\n", "\n", text)

        return text.strip()
