"""
Table Schemas

Pydantic v2 schemas for structured table extraction from SEC 10-K filings.
RawTable holds the raw HTML fragment; StructuredTable holds the parsed,
typed representation with deterministic text serialisation methods.
"""

from __future__ import annotations

import json

from pydantic import BaseModel, Field


class RawTable(BaseModel):
    """Raw HTML table extracted from a SEC 10-K filing section.

    Attributes:
        html: Raw HTML string of the table element.
        caption: Optional caption text found above or below the table.
        position_in_section: Zero-based ordinal position within the section.
    """

    html: str
    caption: str | None = None
    position_in_section: int


class StructuredTable(BaseModel):
    """Parsed and typed representation of a financial table.

    Attributes:
        title: Human-readable title of the table (e.g. "Consolidated Statements of Income").
        headers: Ordered list of column header labels.
        rows: List of rows; each row is a mapping from header label to cell value.
        footnotes: Optional list of footnote strings attached to the table.
        row_count: Total number of data rows (must equal len(rows)).
        source_section: SEC filing section identifier (e.g. "ITEM_8").
    """

    title: str
    headers: list[str]
    rows: list[dict[str, str]]
    footnotes: list[str] = Field(default_factory=list)
    row_count: int
    source_section: str

    def to_description(self, company: str, fiscal_year: int, section_title: str) -> str:
        """Return a deterministic plain-text description of the table.

        The description is designed to be stored in ``content_raw`` and embedded
        for retrieval. No network or LLM calls are made.

        Format::

            Financial table: {title} | {company} 10-K FY{fiscal_year} | {section_title}
            Columns: {comma-separated headers}
            {up to 10 rows, each as "label: val1, val2, ..."}
            [{N} more rows]  # only if row_count > 10
            Footnotes: {footnote1}; {footnote2}  # only if footnotes present

        Args:
            company: Company name or ticker (e.g. "Apple Inc." or "AAPL").
            fiscal_year: Four-digit fiscal year (e.g. 2024).
            section_title: Human-readable section title (e.g. "Financial Statements").

        Returns:
            A multi-line string description of the table.
        """
        lines: list[str] = [
            f"Financial table: {self.title} | {company} 10-K FY{fiscal_year} | {section_title}",
            f"Columns: {', '.join(self.headers)}",
        ]

        display_rows = self.rows[:10]
        for row in display_rows:
            # First header is typically the row label; remaining headers are value columns.
            if self.headers:
                label = row.get(self.headers[0], "")
                values = [row.get(h, "") for h in self.headers[1:]]
                if values:
                    lines.append(f"{label}: {', '.join(values)}")
                else:
                    lines.append(label)
            else:
                lines.append(", ".join(row.values()))

        remaining = self.row_count - len(display_rows)
        if remaining > 0:
            lines.append(f"[{remaining} more rows]")

        if self.footnotes:
            lines.append(f"Footnotes: {'; '.join(self.footnotes)}")

        return "\n".join(lines)

    def to_json_str(self) -> str:
        """Serialise headers and rows to a compact JSON string.

        Returns:
            A compact JSON string with keys ``"headers"`` and ``"rows"``.
        """
        return json.dumps({"headers": self.headers, "rows": self.rows}, separators=(",", ":"))
