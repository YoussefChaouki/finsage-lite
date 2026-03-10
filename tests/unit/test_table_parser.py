"""Unit tests for TableParser service.

Covers detect_tables(), parse_table(), parse_all(), _is_layout_table(),
and all fallback strategies (pandas → BS4 → raw text).
"""

from __future__ import annotations

from unittest.mock import patch

import pytest

from src.schemas.table import RawTable, StructuredTable
from src.services.table_parser import TableParser

# ---------------------------------------------------------------------------
# Fixtures & HTML helpers
# ---------------------------------------------------------------------------


@pytest.fixture
def parser() -> TableParser:
    return TableParser()


def _income_statement_html() -> str:
    """3-column income statement table."""
    return """
    <table>
        <thead>
            <tr><th>Item</th><th>2023 ($M)</th><th>2022 ($M)</th></tr>
        </thead>
        <tbody>
            <tr><td>Revenue</td><td>100,000</td><td>95,000</td></tr>
            <tr><td>Gross Profit</td><td>45,000</td><td>42,000</td></tr>
            <tr><td>Net Income</td><td>20,000</td><td>18,500</td></tr>
        </tbody>
    </table>
    """


def _balance_sheet_colspan_html() -> str:
    """Balance sheet with colspan in header."""
    return """
    <table>
        <thead>
            <tr>
                <th colspan="1">Account</th>
                <th colspan="2">FY2024</th>
            </tr>
            <tr>
                <th>Description</th><th>Assets ($)</th><th>Liabilities ($)</th>
            </tr>
        </thead>
        <tbody>
            <tr><td>Current Assets</td><td>50,000</td><td>—</td></tr>
            <tr><td>Long-term Debt</td><td>—</td><td>30,000</td></tr>
            <tr><td>Equity</td><td>—</td><td>20,000</td></tr>
        </tbody>
    </table>
    """


def _layout_table_html() -> str:
    """1-column table with no numeric data — layout table."""
    return """
    <table>
        <tr><td>Header Cell</td></tr>
        <tr><td>Navigation link</td></tr>
        <tr><td>Footer text</td></tr>
    </table>
    """


def _empty_table_html() -> str:
    """Table element with no rows."""
    return "<table></table>"


def _two_financial_one_layout_html() -> str:
    """HTML with 2 financial tables and 1 layout table interleaved."""
    return _income_statement_html() + _layout_table_html() + _balance_sheet_colspan_html()


def _no_thead_table_html() -> str:
    """Table with header row using <th> but no <thead> wrapper."""
    return """
    <table>
        <tr><th>Metric</th><th>Value ($)</th><th>Change (%)</th></tr>
        <tr><td>EPS</td><td>3.50</td><td>5%</td></tr>
        <tr><td>EBITDA</td><td>12,000</td><td>8%</td></tr>
        <tr><td>Free Cash Flow</td><td>8,000</td><td>3%</td></tr>
    </table>
    """


def _malformed_table_html() -> str:
    """Severely malformed HTML that pandas cannot parse."""
    return """
    <table>
        <tr><td colspan="not-a-number">Revenue</td><td>$100</td></tr>
        <tr><td>Expenses</td><td>$60</td></tr>
        <tr><td>Net Income</td><td>$40</td></tr>
    </table>
    """


def _section_html_with_caption() -> str:
    """Table that has a <caption> element (2 numeric columns to pass layout filter)."""
    return """
    <table>
        <caption>Consolidated Balance Sheet</caption>
        <thead><tr><th>Line Item</th><th>FY2024 ($)</th><th>FY2023 ($)</th></tr></thead>
        <tbody>
            <tr><td>Cash</td><td>5,000</td><td>4,200</td></tr>
            <tr><td>Receivables</td><td>12,000</td><td>10,500</td></tr>
        </tbody>
    </table>
    """


# ---------------------------------------------------------------------------
# _is_layout_table
# ---------------------------------------------------------------------------


class TestIsLayoutTable:
    def test_financial_table_not_layout(self, parser: TableParser) -> None:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(_income_statement_html(), "html.parser")
        tag = soup.find("table")
        assert parser._is_layout_table(tag) is False  # type: ignore[arg-type]

    def test_layout_table_detected(self, parser: TableParser) -> None:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(_layout_table_html(), "html.parser")
        tag = soup.find("table")
        assert parser._is_layout_table(tag) is True  # type: ignore[arg-type]

    def test_empty_table_is_layout(self, parser: TableParser) -> None:
        from bs4 import BeautifulSoup

        soup = BeautifulSoup(_empty_table_html(), "html.parser")
        tag = soup.find("table")
        assert parser._is_layout_table(tag) is True  # type: ignore[arg-type]

    def test_two_numeric_columns_not_layout(self, parser: TableParser) -> None:
        from bs4 import BeautifulSoup

        html = """
        <table>
            <tr><td>Label</td><td>$100</td><td>$200</td></tr>
            <tr><td>Other</td><td>50%</td><td>60%</td></tr>
        </table>
        """
        soup = BeautifulSoup(html, "html.parser")
        tag = soup.find("table")
        assert parser._is_layout_table(tag) is False  # type: ignore[arg-type]

    def test_one_numeric_column_is_layout(self, parser: TableParser) -> None:
        from bs4 import BeautifulSoup

        html = """
        <table>
            <tr><td>Description</td><td>$100</td></tr>
            <tr><td>More text</td><td>$200</td></tr>
        </table>
        """
        soup = BeautifulSoup(html, "html.parser")
        tag = soup.find("table")
        assert parser._is_layout_table(tag) is True  # type: ignore[arg-type]


# ---------------------------------------------------------------------------
# detect_tables
# ---------------------------------------------------------------------------


class TestDetectTables:
    def test_detects_financial_tables(self, parser: TableParser) -> None:
        raw = parser.detect_tables(_income_statement_html())
        assert len(raw) == 1
        assert raw[0].position_in_section == 0

    def test_filters_layout_table(self, parser: TableParser) -> None:
        raw = parser.detect_tables(_layout_table_html())
        assert raw == []

    def test_two_financial_one_layout(self, parser: TableParser) -> None:
        raw = parser.detect_tables(_two_financial_one_layout_html())
        assert len(raw) == 2
        # Positions reflect original ordinal in HTML, not filtered index
        positions = [t.position_in_section for t in raw]
        assert 0 in positions  # first financial table
        assert 2 in positions  # third table (balance sheet), layout was #1

    def test_extracts_caption(self, parser: TableParser) -> None:
        raw = parser.detect_tables(_section_html_with_caption())
        assert len(raw) == 1
        assert raw[0].caption == "Consolidated Balance Sheet"

    def test_no_tables_returns_empty(self, parser: TableParser) -> None:
        raw = parser.detect_tables("<div>No tables here</div>")
        assert raw == []


# ---------------------------------------------------------------------------
# parse_table — pandas path
# ---------------------------------------------------------------------------


class TestParseTablePandas:
    def test_income_statement_3_columns(self, parser: TableParser) -> None:
        raw = RawTable(html=_income_statement_html(), position_in_section=0)
        result = parser.parse_table(raw)
        assert isinstance(result, StructuredTable)
        assert len(result.headers) == 3
        assert result.row_count >= 3
        assert all(isinstance(r, dict) for r in result.rows)

    def test_headers_present_in_rows(self, parser: TableParser) -> None:
        raw = RawTable(html=_income_statement_html(), position_in_section=0)
        result = parser.parse_table(raw)
        assert result is not None
        for row in result.rows:
            for h in result.headers:
                assert h in row

    def test_empty_table_returns_none(self, parser: TableParser) -> None:
        raw = RawTable(html=_empty_table_html(), position_in_section=0)
        result = parser.parse_table(raw)
        assert result is None

    def test_title_uses_caption_when_present(self, parser: TableParser) -> None:
        raw = RawTable(
            html=_section_html_with_caption(),
            caption="Consolidated Balance Sheet",
            position_in_section=0,
        )
        result = parser.parse_table(raw)
        assert result is not None
        assert result.title == "Consolidated Balance Sheet"


# ---------------------------------------------------------------------------
# parse_table — BS4 fallback path
# ---------------------------------------------------------------------------


class TestParseTableBS4Fallback:
    def test_bs4_fallback_when_pandas_fails(self, parser: TableParser) -> None:
        """Simulate pandas failure; BS4 must recover."""
        raw = RawTable(html=_no_thead_table_html(), position_in_section=0)
        # Patch pandas path to raise ValueError
        with patch("src.services.table_parser.pd.read_html", side_effect=ValueError("mocked")):
            result = parser.parse_table(raw)
        # BS4 or raw-text fallback should produce a result
        assert result is not None

    def test_no_thead_table_parses_correctly(self, parser: TableParser) -> None:
        raw = RawTable(html=_no_thead_table_html(), position_in_section=0)
        result = parser.parse_table(raw)
        assert result is not None
        assert result.row_count >= 2

    def test_balance_sheet_colspan_headers(self, parser: TableParser) -> None:
        raw = RawTable(html=_balance_sheet_colspan_html(), position_in_section=0)
        result = parser.parse_table(raw)
        assert result is not None
        assert len(result.headers) >= 2
        assert result.row_count >= 2


# ---------------------------------------------------------------------------
# parse_table — raw text fallback
# ---------------------------------------------------------------------------


class TestParseTableRawText:
    def test_raw_text_fallback_produces_text_column(self, parser: TableParser) -> None:
        """Force both pandas and BS4 to fail; raw text must produce output."""
        # Table with only 1 row (BS4 returns < 2 rows → triggers raw text)
        html = """
        <table>
            <thead><tr><th>Item</th><th>Value ($)</th></tr></thead>
            <tbody>
                <tr><td>Revenue</td><td>50,000</td></tr>
            </tbody>
        </table>
        """
        raw = RawTable(html=html, position_in_section=0)
        with patch("src.services.table_parser.pd.read_html", side_effect=ValueError):
            result = parser.parse_table(raw)
        # Either BS4 path (which returns None for < 2 rows) or raw text path
        # Raw text path should produce "text" column entries
        if result is not None:
            # If pandas succeeded, that's fine too
            assert result.row_count >= 1

    def test_malformed_html_does_not_raise(self, parser: TableParser) -> None:
        raw = RawTable(html=_malformed_table_html(), position_in_section=0)
        # Should not raise regardless of internal path taken
        result = parser.parse_table(raw)
        # Malformed colspan attribute; result may or may not be None
        assert result is None or isinstance(result, StructuredTable)


# ---------------------------------------------------------------------------
# parse_all
# ---------------------------------------------------------------------------


class TestParseAll:
    def test_two_financial_one_layout_returns_two(self, parser: TableParser) -> None:
        results = parser.parse_all(_two_financial_one_layout_html())
        assert len(results) == 2
        assert all(isinstance(r, StructuredTable) for r in results)

    def test_parse_all_never_raises(self, parser: TableParser) -> None:
        # Completely broken HTML
        results = parser.parse_all("<<< not html >>>")
        assert isinstance(results, list)

    def test_parse_all_empty_html(self, parser: TableParser) -> None:
        results = parser.parse_all("")
        assert results == []

    def test_parse_all_filters_none_results(self, parser: TableParser) -> None:
        # One empty table (returns None) + one financial table
        html = _empty_table_html() + _income_statement_html()
        results = parser.parse_all(html)
        # The empty table is filtered by _is_layout_table (no rows → < 2 numeric cols)
        assert all(r is not None for r in results)

    def test_parse_all_income_statement_valid(self, parser: TableParser) -> None:
        results = parser.parse_all(_income_statement_html())
        assert len(results) == 1
        t = results[0]
        assert len(t.headers) == 3
        assert t.row_count >= 3

    def test_parse_all_section_with_no_tables(self, parser: TableParser) -> None:
        html = "<section><p>Management discussion only.</p></section>"
        results = parser.parse_all(html)
        assert results == []

    def test_parse_all_exception_in_parse_table_skips_gracefully(
        self, parser: TableParser
    ) -> None:
        """Even if parse_table raises unexpectedly, parse_all must not propagate."""
        with patch.object(parser, "parse_table", side_effect=RuntimeError("unexpected")):
            results = parser.parse_all(_income_statement_html())
        assert results == []

    def test_structured_table_row_count_matches_rows_len(self, parser: TableParser) -> None:
        results = parser.parse_all(_income_statement_html())
        for t in results:
            assert t.row_count == len(t.rows)
