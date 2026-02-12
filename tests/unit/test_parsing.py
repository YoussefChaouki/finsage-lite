"""
Unit tests for HTML Parser + Section Splitter.

Tests both synthetic minimal HTML and the real AAPL filing.
"""

import re
from pathlib import Path

import pytest

from src.models.chunk import SectionType
from src.services.parsing import FilingParser, ParsingError

AAPL_FILING_PATH = Path("data/filings/0000320193_0000320193-25-000079.html")

# Minimal synthetic 10-K HTML mimicking iXBRL format
MINIMAL_10K_HTML = """\
<?xml version='1.0'?>
<html xmlns="http://www.w3.org/1999/xhtml"
      xmlns:ix="http://www.xbrl.org/2013/inlineXBRL">
<head><title>test-20240928</title></head>
<body>
  <div style="display:none"><ix:header><ix:hidden>
    <ix:nonNumeric name="dei:EntityRegistrantName">Test Corp</ix:nonNumeric>
    <ix:nonNumeric name="dei:EntityCentralIndexKey">0001234567</ix:nonNumeric>
    <ix:nonNumeric name="dei:DocumentFiscalYearFocus">2024</ix:nonNumeric>
    <ix:nonNumeric name="dei:DocumentFiscalPeriodFocus">FY</ix:nonNumeric>
  </ix:hidden></ix:header></div>

  <!-- TOC table (should be ignored) -->
  <div><table><tr><td>
    <span style="font-weight:700"><a href="#s1">Item 1.</a></span>
  </td></tr></table></div>
  <div><table><tr><td>
    <span style="font-weight:700"><a href="#s7">Item 7.</a></span>
  </td></tr></table></div>

  <!-- PART I heading (not an Item) -->
  <div><span style="font-weight:700">PART I</span></div>

  <!-- Item 1 -->
  <div style="padding-left:45pt;text-indent:-45pt">
    <span style="font-weight:700">Item 1.\u00a0\u00a0Business</span>
  </div>
  <div>This is the business section content for Test Corp.</div>
  <div>It describes the company operations.</div>
  <div>Test Corp | 2024 Form 10-K | 1</div>

  <!-- Item 1A -->
  <div style="padding-left:45pt;text-indent:-45pt">
    <span style="font-weight:700">Item 1A.\u00a0\u00a0Risk Factors</span>
  </div>
  <div>Risk factor content here.</div>
  <div>The company faces various risks.</div>

  <!-- Item 7 -->
  <div style="padding-left:45pt;text-indent:-45pt">
    <span style="font-weight:700">Item 7.\u00a0\u00a0MD&amp;A</span>
  </div>
  <div>Management discussion content.</div>
  <div><table><tr><td>Revenue</td><td>$100M</td></tr></table></div>
  <div>Test Corp | 2024 Form 10-K | 5</div>

  <!-- Item 7A -->
  <div style="padding-left:45pt;text-indent:-45pt">
    <span style="font-weight:700">Item 7A.\u00a0\u00a0Market Risk</span>
  </div>
  <div>Market risk disclosures here.</div>

  <!-- Item 8 -->
  <div style="padding-left:45pt;text-indent:-45pt">
    <span style="font-weight:700">Item 8.\u00a0\u00a0Financial Statements</span>
  </div>
  <div>Financial statements and supplementary data.</div>
  <div>Table of Contents</div>
  <div>42</div>

  <!-- Item 9 (not a target, used as boundary for Item 8) -->
  <div style="padding-left:45pt;text-indent:-45pt">
    <span style="font-weight:700">Item 9.\u00a0\u00a0Changes in Accountants</span>
  </div>
  <div>Not a target section content.</div>
</body></html>
"""


@pytest.fixture()
def parser() -> FilingParser:
    """Pre-configured FilingParser with default target sections."""
    return FilingParser()


@pytest.fixture()
def minimal_filing(tmp_path: Path) -> Path:
    """Write minimal 10-K HTML to a temp file and return its path."""
    filepath = tmp_path / "test_filing.html"
    filepath.write_text(MINIMAL_10K_HTML, encoding="utf-8")
    return filepath


# --- Metadata extraction ---


def test_extract_metadata_from_ixbrl(parser: FilingParser, minimal_filing: Path) -> None:
    """iXBRL dei fields are parsed correctly."""
    result = parser.parse_html(minimal_filing)
    assert result.metadata.company_name == "Test Corp"
    assert result.metadata.cik == "0001234567"
    assert result.metadata.fiscal_year == 2024
    assert result.metadata.filing_period == "FY"


def test_extract_metadata_doc_title(parser: FilingParser, minimal_filing: Path) -> None:
    """HTML <title> tag is extracted."""
    result = parser.parse_html(minimal_filing)
    assert result.metadata.doc_title == "test-20240928"


def test_extract_metadata_missing_fields(tmp_path: Path) -> None:
    """Graceful fallback when dei fields are absent."""
    html = "<html><head><title>no-dei</title></head><body>"
    html += '<div><span style="font-weight:700">Item 1.\u00a0\u00a0Business</span></div>'
    html += "<div>Content here.</div>"
    html += '<div><span style="font-weight:700">Item 2.\u00a0\u00a0Properties</span></div>'
    html += "</body></html>"
    filepath = tmp_path / "no_dei.html"
    filepath.write_text(html, encoding="utf-8")

    parser = FilingParser(target_sections=["1"])
    result = parser.parse_html(filepath)
    assert result.metadata.company_name == ""
    assert result.metadata.cik == ""
    assert result.metadata.fiscal_year == 0


# --- Section detection ---


def test_find_headings_all_items_detected(parser: FilingParser, minimal_filing: Path) -> None:
    """All 6 Item headings (1, 1A, 7, 7A, 8, 9) are detected."""
    result = parser.parse_html(minimal_filing)
    assert len(result.all_sections_found) == 6


def test_find_headings_excludes_toc(parser: FilingParser, minimal_filing: Path) -> None:
    """TOC entries inside <td> are not detected as headings."""
    result = parser.parse_html(minimal_filing)
    # TOC has Item 1 and Item 7, so total detected should NOT be 8
    assert len(result.all_sections_found) == 6


def test_find_headings_sequential_order(parser: FilingParser, minimal_filing: Path) -> None:
    """Headings appear in sequential document order."""
    result = parser.parse_html(minimal_filing)
    item_nums = []
    for heading_str in result.all_sections_found:
        # Parse "Item 1A: Risk Factors" -> "1A"
        match = re.match(r"Item (\S+):", heading_str)
        if match:
            item_nums.append(match.group(1).lower())

    expected_order = ["1", "1a", "7", "7a", "8", "9"]
    assert item_nums == expected_order


def test_find_headings_empty_html(tmp_path: Path) -> None:
    """No headings in empty HTML raises ParsingError."""
    filepath = tmp_path / "empty.html"
    filepath.write_text("<html><body><div>No items here.</div></body></html>")
    parser = FilingParser()
    with pytest.raises(ParsingError, match="No section headings found"):
        parser.parse_html(filepath)


# --- Content extraction ---


def test_extract_section_content_basic(parser: FilingParser, minimal_filing: Path) -> None:
    """Text is extracted between two headings."""
    result = parser.parse_html(minimal_filing)
    item1 = result.sections[SectionType.ITEM_1]
    assert "business section content" in item1.text_content.lower()
    assert "company operations" in item1.text_content.lower()


def test_extract_section_html_preserved(parser: FilingParser, minimal_filing: Path) -> None:
    """HTML content includes table markup for downstream parsing."""
    result = parser.parse_html(minimal_filing)
    item7 = result.sections[SectionType.ITEM_7]
    assert "<table>" in item7.html_content or "<table" in item7.html_content


def test_extract_section_last_item_boundary(parser: FilingParser, minimal_filing: Path) -> None:
    """Item 8 content does not leak into Item 9 content."""
    result = parser.parse_html(minimal_filing)
    item8 = result.sections[SectionType.ITEM_8]
    assert "Financial statements" in item8.text_content
    assert "Not a target section" not in item8.text_content


# --- Text cleanup ---


def test_clean_text_removes_page_footers(parser: FilingParser, minimal_filing: Path) -> None:
    """Page footers like 'Company | Year Form 10-K | N' are removed."""
    result = parser.parse_html(minimal_filing)
    item1 = result.sections[SectionType.ITEM_1]
    assert "Test Corp | 2024 Form 10-K" not in item1.text_content


def test_clean_text_removes_toc_header(parser: FilingParser, minimal_filing: Path) -> None:
    """'Table of Contents' lines are removed."""
    result = parser.parse_html(minimal_filing)
    item8 = result.sections[SectionType.ITEM_8]
    assert "Table of Contents" not in item8.text_content


def test_clean_text_normalizes_whitespace(parser: FilingParser, minimal_filing: Path) -> None:
    """Non-breaking spaces are normalized to regular spaces."""
    result = parser.parse_html(minimal_filing)
    for section in result.sections.values():
        assert "\xa0" not in section.text_content


def test_clean_text_removes_standalone_page_numbers(
    parser: FilingParser, minimal_filing: Path
) -> None:
    """Standalone page numbers are removed."""
    result = parser.parse_html(minimal_filing)
    item8 = result.sections[SectionType.ITEM_8]
    # "42" was a standalone page number
    lines = [line.strip() for line in item8.text_content.split("\n") if line.strip()]
    assert "42" not in lines


# --- Full pipeline ---


def test_parse_html_all_five_target_sections(parser: FilingParser, minimal_filing: Path) -> None:
    """All 5 target sections are extracted."""
    result = parser.parse_html(minimal_filing)
    expected = {
        SectionType.ITEM_1,
        SectionType.ITEM_1A,
        SectionType.ITEM_7,
        SectionType.ITEM_7A,
        SectionType.ITEM_8,
    }
    assert set(result.sections.keys()) == expected


def test_parse_html_no_residual_html(parser: FilingParser, minimal_filing: Path) -> None:
    """No HTML tags remain in text_content."""
    result = parser.parse_html(minimal_filing)
    html_tag_re = re.compile(r"</?[a-z][a-z0-9]*[\s>]", re.IGNORECASE)
    for section_type, section in result.sections.items():
        assert not html_tag_re.search(section.text_content), (
            f"Residual HTML in {section_type}: {html_tag_re.findall(section.text_content)[:3]}"
        )


def test_parse_html_section_titles(parser: FilingParser, minimal_filing: Path) -> None:
    """Section titles are correctly extracted."""
    result = parser.parse_html(minimal_filing)
    assert result.sections[SectionType.ITEM_1].title == "Business"
    assert result.sections[SectionType.ITEM_1A].title == "Risk Factors"
    assert result.sections[SectionType.ITEM_8].title == "Financial Statements"


def test_parse_html_file_not_found(parser: FilingParser) -> None:
    """FileNotFoundError raised for missing file."""
    with pytest.raises(FileNotFoundError):
        parser.parse_html(Path("/nonexistent/filing.html"))


def test_parse_html_empty_file(parser: FilingParser, tmp_path: Path) -> None:
    """ParsingError raised for empty file."""
    filepath = tmp_path / "empty.html"
    filepath.write_text("")
    with pytest.raises(ParsingError, match="Empty file"):
        parser.parse_html(filepath)


# --- Real AAPL filing tests ---


@pytest.mark.skipif(
    not AAPL_FILING_PATH.exists(),
    reason="AAPL filing not available locally",
)
class TestAAPLFiling:
    """Tests against the real Apple 10-K filing."""

    def test_all_five_sections_detected(self) -> None:
        """All 5 target sections are detected in the AAPL filing."""
        parser = FilingParser()
        result = parser.parse_html(AAPL_FILING_PATH)
        expected = {
            SectionType.ITEM_1,
            SectionType.ITEM_1A,
            SectionType.ITEM_7,
            SectionType.ITEM_7A,
            SectionType.ITEM_8,
        }
        assert set(result.sections.keys()) == expected

    def test_metadata_extracted(self) -> None:
        """Metadata matches expected Apple filing data."""
        parser = FilingParser()
        result = parser.parse_html(AAPL_FILING_PATH)
        assert result.metadata.company_name == "Apple Inc."
        assert result.metadata.cik == "0000320193"
        assert result.metadata.fiscal_year == 2025
        assert result.metadata.filing_period == "FY"
        assert "aapl" in result.metadata.doc_title.lower()

    def test_no_residual_html(self) -> None:
        """No HTML tags in any section's text_content."""
        parser = FilingParser()
        result = parser.parse_html(AAPL_FILING_PATH)
        html_tag_re = re.compile(r"</?[a-z][a-z0-9]*[\s>]", re.IGNORECASE)
        for section_type, section in result.sections.items():
            assert not html_tag_re.search(section.text_content), f"Residual HTML in {section_type}"

    def test_item1_starts_with_company_background(self) -> None:
        """Item 1 text begins with 'Company Background'."""
        parser = FilingParser()
        result = parser.parse_html(AAPL_FILING_PATH)
        item1_text = result.sections[SectionType.ITEM_1].text_content
        assert item1_text.startswith("Company Background")

    def test_item7_has_substantial_content(self) -> None:
        """Item 7 (MD&A) has significant text content."""
        parser = FilingParser()
        result = parser.parse_html(AAPL_FILING_PATH)
        item7_text = result.sections[SectionType.ITEM_7].text_content
        assert len(item7_text) > 1000

    def test_section_titles_correct(self) -> None:
        """Section titles match expected 10-K standard names."""
        parser = FilingParser()
        result = parser.parse_html(AAPL_FILING_PATH)
        assert result.sections[SectionType.ITEM_1].title == "Business"
        assert result.sections[SectionType.ITEM_1A].title == "Risk Factors"
        assert "Management" in result.sections[SectionType.ITEM_7].title
        assert "Market Risk" in result.sections[SectionType.ITEM_7A].title
        assert "Financial Statements" in result.sections[SectionType.ITEM_8].title

    def test_no_page_footers_in_content(self) -> None:
        """Page footers are stripped from all sections."""
        parser = FilingParser()
        result = parser.parse_html(AAPL_FILING_PATH)
        for section in result.sections.values():
            assert "Apple Inc. | 2025 Form 10-K |" not in section.text_content

    def test_all_headings_found(self) -> None:
        """All standard 10-K Items are detected (not just targets)."""
        parser = FilingParser()
        result = parser.parse_html(AAPL_FILING_PATH)
        # AAPL filing has Items 1 through 16
        assert len(result.all_sections_found) >= 16
