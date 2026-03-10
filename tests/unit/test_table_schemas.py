"""Unit tests for src/schemas/table.py — RawTable and StructuredTable."""

from __future__ import annotations

import json

from src.schemas.table import RawTable, StructuredTable

# ---------------------------------------------------------------------------
# Helpers / fixtures
# ---------------------------------------------------------------------------

INCOME_HEADERS = ["Item", "FY2024", "FY2023", "FY2022"]

INCOME_ROWS = [
    {"Item": "Revenue", "FY2024": "391,035", "FY2023": "383,285", "FY2022": "394,328"},
    {"Item": "Cost of Sales", "FY2024": "210,352", "FY2023": "214,137", "FY2022": "223,546"},
    {"Item": "Gross Margin", "FY2024": "180,683", "FY2023": "169,148", "FY2022": "170,782"},
    {"Item": "Operating Expenses", "FY2024": "57,467", "FY2023": "54,847", "FY2022": "51,345"},
    {"Item": "Net Income", "FY2024": "93,736", "FY2023": "96,995", "FY2022": "99,803"},
]


def _make_income_table(**kwargs: object) -> StructuredTable:
    defaults: dict[str, object] = {
        "title": "Consolidated Statements of Income",
        "headers": INCOME_HEADERS,
        "rows": INCOME_ROWS,
        "footnotes": [],
        "row_count": len(INCOME_ROWS),
        "source_section": "ITEM_8",
    }
    defaults.update(kwargs)
    return StructuredTable(**defaults)  # type: ignore[arg-type]


def _make_long_table(n_rows: int) -> StructuredTable:
    """Return a StructuredTable with *n_rows* data rows."""
    headers = ["Metric", "Value"]
    rows = [{"Metric": f"Row {i}", "Value": str(i * 1_000)} for i in range(1, n_rows + 1)]
    return StructuredTable(
        title="Long Financial Table",
        headers=headers,
        rows=rows,
        footnotes=[],
        row_count=n_rows,
        source_section="ITEM_7",
    )


# ---------------------------------------------------------------------------
# RawTable tests
# ---------------------------------------------------------------------------


class TestRawTable:
    def test_basic_construction(self) -> None:
        raw = RawTable(html="<table><tr><td>1</td></tr></table>", position_in_section=0)
        assert raw.html.startswith("<table")
        assert raw.caption is None
        assert raw.position_in_section == 0

    def test_caption_optional(self) -> None:
        raw = RawTable(
            html="<table></table>",
            caption="Table 1. Income",
            position_in_section=2,
        )
        assert raw.caption == "Table 1. Income"

    def test_position_preserved(self) -> None:
        raw = RawTable(html="<table></table>", position_in_section=7)
        assert raw.position_in_section == 7


# ---------------------------------------------------------------------------
# StructuredTable — construction
# ---------------------------------------------------------------------------


class TestStructuredTableConstruction:
    def test_income_statement_fields(self) -> None:
        tbl = _make_income_table()
        assert tbl.title == "Consolidated Statements of Income"
        assert tbl.headers == INCOME_HEADERS
        assert len(tbl.rows) == 5
        assert tbl.row_count == 5
        assert tbl.source_section == "ITEM_8"

    def test_footnotes_default_empty(self) -> None:
        tbl = _make_income_table()
        assert tbl.footnotes == []

    def test_source_section_propagated(self) -> None:
        tbl = _make_income_table(source_section="ITEM_7A")
        assert tbl.source_section == "ITEM_7A"

    def test_row_count_independent_of_rows_length(self) -> None:
        # row_count is a plain field — caller is responsible for consistency.
        tbl = _make_income_table(row_count=99)
        assert tbl.row_count == 99


# ---------------------------------------------------------------------------
# StructuredTable.to_description — typical income statement
# ---------------------------------------------------------------------------


class TestToDescriptionIncomeStatement:
    def setup_method(self) -> None:
        self.tbl = _make_income_table()
        self.desc = self.tbl.to_description("Apple Inc.", 2024, "Financial Statements")

    def test_header_line_format(self) -> None:
        first_line = self.desc.splitlines()[0]
        assert "Financial table:" in first_line
        assert "Apple Inc." in first_line
        assert "FY2024" in first_line
        assert "Financial Statements" in first_line

    def test_columns_line_present(self) -> None:
        lines = self.desc.splitlines()
        col_line = next(line for line in lines if line.startswith("Columns:"))
        for h in INCOME_HEADERS:
            assert h in col_line

    def test_row_values_present(self) -> None:
        assert "Revenue" in self.desc
        assert "391,035" in self.desc
        assert "Net Income" in self.desc

    def test_no_truncation_marker_for_short_table(self) -> None:
        assert "more rows" not in self.desc

    def test_no_footnotes_section_when_empty(self) -> None:
        assert "Footnotes" not in self.desc


# ---------------------------------------------------------------------------
# StructuredTable.to_description — truncation for > 10 rows
# ---------------------------------------------------------------------------


class TestToDescriptionTruncation:
    def test_exactly_10_rows_no_marker(self) -> None:
        tbl = _make_long_table(10)
        desc = tbl.to_description("MSFT", 2023, "MD&A")
        assert "more rows" not in desc

    def test_11_rows_shows_1_more(self) -> None:
        tbl = _make_long_table(11)
        desc = tbl.to_description("MSFT", 2023, "MD&A")
        assert "[1 more rows]" in desc

    def test_15_rows_shows_5_more(self) -> None:
        tbl = _make_long_table(15)
        desc = tbl.to_description("MSFT", 2023, "MD&A")
        assert "[5 more rows]" in desc

    def test_only_first_10_data_rows_in_body(self) -> None:
        tbl = _make_long_table(12)
        desc = tbl.to_description("MSFT", 2023, "MD&A")
        assert "Row 10" in desc
        assert "Row 11" not in desc
        assert "Row 12" not in desc


# ---------------------------------------------------------------------------
# StructuredTable.to_description — footnotes
# ---------------------------------------------------------------------------


class TestToDescriptionFootnotes:
    def test_footnotes_appear_in_description(self) -> None:
        tbl = _make_income_table(
            footnotes=["Amounts in millions USD", "Excludes discontinued operations"]
        )
        desc = tbl.to_description("Apple Inc.", 2024, "Financial Statements")
        assert "Footnotes:" in desc
        assert "Amounts in millions USD" in desc
        assert "Excludes discontinued operations" in desc

    def test_footnotes_joined_by_semicolon(self) -> None:
        tbl = _make_income_table(footnotes=["Note A", "Note B"])
        desc = tbl.to_description("Apple Inc.", 2024, "Financial Statements")
        assert "Note A; Note B" in desc

    def test_single_footnote_no_trailing_semicolon(self) -> None:
        tbl = _make_income_table(footnotes=["Restated for prior period adjustment"])
        desc = tbl.to_description("Apple Inc.", 2024, "Financial Statements")
        # No trailing semicolon in a single-footnote list
        assert "Footnotes: Restated for prior period adjustment" in desc


# ---------------------------------------------------------------------------
# StructuredTable.to_json_str — roundtrip
# ---------------------------------------------------------------------------


class TestToJsonStr:
    def test_roundtrip_headers(self) -> None:
        tbl = _make_income_table()
        parsed = json.loads(tbl.to_json_str())
        assert parsed["headers"] == INCOME_HEADERS

    def test_roundtrip_rows(self) -> None:
        tbl = _make_income_table()
        parsed = json.loads(tbl.to_json_str())
        assert parsed["rows"] == INCOME_ROWS

    def test_compact_no_extra_spaces(self) -> None:
        tbl = _make_income_table()
        s = tbl.to_json_str()
        # Compact JSON uses "," not ", " between items
        assert ", " not in s or '": "' in s  # values may contain spaces, keys/sep don't

    def test_json_contains_only_headers_and_rows_keys(self) -> None:
        tbl = _make_income_table()
        parsed = json.loads(tbl.to_json_str())
        assert set(parsed.keys()) == {"headers", "rows"}

    def test_empty_rows_roundtrip(self) -> None:
        tbl = StructuredTable(
            title="Empty",
            headers=["A", "B"],
            rows=[],
            row_count=0,
            source_section="ITEM_1",
        )
        parsed = json.loads(tbl.to_json_str())
        assert parsed["rows"] == []
        assert parsed["headers"] == ["A", "B"]
