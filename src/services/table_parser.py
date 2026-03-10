"""Table Parser Service

Stateless service for extracting and parsing financial HTML tables from
SEC 10-K filing sections. Robustness is paramount: EDGAR HTML structures
vary widely across filers and years.
"""

from __future__ import annotations

import io
import logging
import re
from typing import TYPE_CHECKING

import pandas as pd
from bs4 import BeautifulSoup, Tag

from src.schemas.table import RawTable, StructuredTable

if TYPE_CHECKING:
    pass

logger = logging.getLogger(__name__)

# Regex to detect numeric / financial data in a cell
_NUMERIC_RE = re.compile(r"[\d\$\%]")


class TableParser:
    """Stateless parser for HTML financial tables.

    All methods are synchronous (no I/O). Thread-safe; a single instance can
    be shared across async handlers.
    """

    # ------------------------------------------------------------------ #
    # Public API                                                           #
    # ------------------------------------------------------------------ #

    def detect_tables(self, html_content: str) -> list[RawTable]:
        """Detect financial tables in an HTML section fragment.

        Finds all ``<table>`` elements, filters layout tables via
        :meth:`_is_layout_table`, and returns :class:`RawTable` objects
        with their ordinal position preserved.

        Args:
            html_content: Raw HTML string for one SEC 10-K section.

        Returns:
            Ordered list of :class:`RawTable` objects (layout tables excluded).
        """
        soup = BeautifulSoup(html_content, "html.parser")
        raw_tables: list[RawTable] = []
        position = 0

        for tag in soup.find_all("table"):
            if not isinstance(tag, Tag):
                continue
            if self._is_layout_table(tag):
                logger.debug("Skipping layout table at raw position %d", position)
                position += 1
                continue

            caption = self._extract_caption(tag)
            raw_tables.append(
                RawTable(
                    html=str(tag),
                    caption=caption,
                    position_in_section=position,
                )
            )
            position += 1

        return raw_tables

    def parse_table(self, raw_table: RawTable) -> StructuredTable | None:
        """Parse a single :class:`RawTable` into a :class:`StructuredTable`.

        Uses a three-step fallback chain:

        1. ``pandas.read_html()`` — handles most well-formed tables.
        2. BeautifulSoup custom extraction — handles tables that confuse pandas
           (missing ``<tbody>``, merged header cells, etc.).
        3. Raw text extraction — last resort; produces a single ``"text"``
           column.

        Returns ``None`` (and logs a warning) if all steps fail so that callers
        are never surprised by an exception.

        Args:
            raw_table: The :class:`RawTable` to parse.

        Returns:
            A :class:`StructuredTable` or ``None`` if parsing failed entirely.
        """
        # Step 1 — pandas
        result = self._parse_with_pandas(raw_table)
        if result is not None:
            return result

        # Step 2 — BeautifulSoup custom
        result = self._parse_with_bs4(raw_table)
        if result is not None:
            return result

        # Step 3 — raw text extraction
        result = self._parse_raw_text(raw_table)
        if result is not None:
            return result

        logger.warning(
            "All parse strategies failed for table at position %d",
            raw_table.position_in_section,
        )
        return None

    def parse_all(self, html_content: str) -> list[StructuredTable]:
        """Full pipeline: detect tables then parse each one.

        This method **never raises**. Individual table failures are logged and
        skipped.

        Args:
            html_content: Raw HTML string for one SEC 10-K section.

        Returns:
            List of successfully parsed :class:`StructuredTable` objects.
        """
        try:
            raw_tables = self.detect_tables(html_content)
        except Exception:
            logger.exception("detect_tables raised unexpectedly; returning empty list")
            return []

        structured: list[StructuredTable] = []
        for raw in raw_tables:
            try:
                result = self.parse_table(raw)
            except Exception:
                logger.exception(
                    "parse_table raised unexpectedly for table at position %d",
                    raw.position_in_section,
                )
                result = None

            if result is not None:
                structured.append(result)

        return structured

    # ------------------------------------------------------------------ #
    # Private helpers                                                      #
    # ------------------------------------------------------------------ #

    def _is_layout_table(self, table_tag: Tag) -> bool:
        """Return ``True`` if the table is a layout (non-data) table.

        A table is considered a layout table when fewer than two of its columns
        contain at least one cell with numeric / financial data (digits, ``$``,
        or ``%``).

        Args:
            table_tag: A BeautifulSoup ``<table>`` Tag.

        Returns:
            ``True`` if the table should be excluded from results.
        """
        rows = table_tag.find_all("tr")
        if not rows:
            return True

        # Build a column → has_numeric mapping
        col_has_numeric: dict[int, bool] = {}

        for row in rows:
            cells = row.find_all(["td", "th"])
            col_idx = 0
            for cell in cells:
                if not isinstance(cell, Tag):
                    col_idx += 1
                    continue
                text = cell.get_text()
                if _NUMERIC_RE.search(text):
                    col_has_numeric[col_idx] = True
                else:
                    col_has_numeric.setdefault(col_idx, False)

                # Advance by colspan
                try:
                    colspan = int(cell.get("colspan", 1))  # type: ignore[arg-type]
                except (ValueError, TypeError):
                    colspan = 1
                col_idx += colspan

        numeric_cols = sum(1 for v in col_has_numeric.values() if v)
        return numeric_cols < 2

    def _extract_caption(self, table_tag: Tag) -> str | None:
        """Extract caption text from a ``<caption>`` element, if present.

        Args:
            table_tag: A BeautifulSoup ``<table>`` Tag.

        Returns:
            Stripped caption text, or ``None``.
        """
        caption_tag = table_tag.find("caption")
        if caption_tag and isinstance(caption_tag, Tag):
            text = caption_tag.get_text(strip=True)
            return text if text else None
        return None

    # ------------------------------------------------------------------ #
    # Parse strategies                                                     #
    # ------------------------------------------------------------------ #

    def _parse_with_pandas(self, raw_table: RawTable) -> StructuredTable | None:
        """Attempt parsing via ``pandas.read_html``.

        Args:
            raw_table: Source :class:`RawTable`.

        Returns:
            :class:`StructuredTable` on success, ``None`` otherwise.
        """
        try:
            dfs = pd.read_html(io.StringIO(raw_table.html))
        except (ValueError, IndexError):
            return None
        except Exception:
            logger.debug("pandas.read_html raised unexpected error", exc_info=True)
            return None

        if not dfs:
            return None

        df = dfs[0]
        # Flatten MultiIndex columns if present
        if isinstance(df.columns, pd.MultiIndex):
            df.columns = [" ".join(str(c) for c in col).strip() for col in df.columns]

        headers = [str(c) for c in df.columns]
        rows: list[dict[str, str]] = []
        for _, row in df.iterrows():
            rows.append(
                {h: str(v) if not pd.isna(v) else "" for h, v in zip(headers, row, strict=False)}
            )

        if not rows:
            return None

        title = raw_table.caption or f"Table {raw_table.position_in_section}"
        return StructuredTable(
            title=title,
            headers=headers,
            rows=rows,
            row_count=len(rows),
            source_section="",
        )

    def _parse_with_bs4(self, raw_table: RawTable) -> StructuredTable | None:
        """Attempt custom BeautifulSoup parsing.

        Extracts headers from ``<thead>`` or the first ``<tr>`` of ``<tbody>``
        (or bare first ``<tr>``). Rows are taken from remaining ``<tr>``
        elements.

        Returns ``None`` when fewer than 2 data rows are extracted (triggers
        the raw-text fallback).

        Args:
            raw_table: Source :class:`RawTable`.

        Returns:
            :class:`StructuredTable` on success, ``None`` when < 2 rows.
        """
        try:
            soup = BeautifulSoup(raw_table.html, "html.parser")
            table_tag = soup.find("table")
            if not isinstance(table_tag, Tag):
                return None

            headers = self._extract_headers_bs4(table_tag)
            body_rows = self._extract_body_rows_bs4(
                table_tag, skip_first_if_no_thead=not bool(table_tag.find("thead"))
            )

            if len(body_rows) < 2:
                return None

            if not headers:
                # Synthesise generic headers
                max_cols = max((len(r) for r in body_rows), default=1)
                headers = [f"col_{i}" for i in range(max_cols)]

            structured_rows: list[dict[str, str]] = []
            for row_cells in body_rows:
                row_dict: dict[str, str] = {}
                for i, header in enumerate(headers):
                    row_dict[header] = row_cells[i] if i < len(row_cells) else ""
                structured_rows.append(row_dict)

            title = raw_table.caption or f"Table {raw_table.position_in_section}"
            return StructuredTable(
                title=title,
                headers=headers,
                rows=structured_rows,
                row_count=len(structured_rows),
                source_section="",
            )
        except Exception:
            logger.debug("BS4 custom parse failed", exc_info=True)
            return None

    def _parse_raw_text(self, raw_table: RawTable) -> StructuredTable | None:
        """Last-resort: extract all cell text into a single ``"text"`` column.

        Args:
            raw_table: Source :class:`RawTable`.

        Returns:
            :class:`StructuredTable` with one ``"text"`` column, or ``None``.
        """
        try:
            soup = BeautifulSoup(raw_table.html, "html.parser")
            table_tag = soup.find("table")
            if not isinstance(table_tag, Tag):
                return None

            rows: list[dict[str, str]] = []
            for tr in table_tag.find_all("tr"):
                if not isinstance(tr, Tag):
                    continue
                for cell in tr.find_all(["td", "th"]):
                    if not isinstance(cell, Tag):
                        continue
                    text = cell.get_text(strip=True)
                    if text:
                        rows.append({"text": text})

            if not rows:
                return None

            title = raw_table.caption or f"Table {raw_table.position_in_section}"
            return StructuredTable(
                title=title,
                headers=["text"],
                rows=rows,
                row_count=len(rows),
                source_section="",
            )
        except Exception:
            logger.debug("Raw text extraction failed", exc_info=True)
            return None

    # ------------------------------------------------------------------ #
    # BS4 sub-helpers                                                      #
    # ------------------------------------------------------------------ #

    def _extract_headers_bs4(self, table_tag: Tag) -> list[str]:
        """Extract column header labels from a ``<thead>`` or first ``<tr>``.

        Args:
            table_tag: BeautifulSoup ``<table>`` Tag.

        Returns:
            List of header label strings (may be empty).
        """
        thead = table_tag.find("thead")
        if thead and isinstance(thead, Tag):
            header_rows = thead.find_all("tr")
            if header_rows:
                # Use only the last row of the thead as the definitive header
                return self._cells_to_text(header_rows[-1])

        # Fall back to first <tr> anywhere in the table
        first_tr = table_tag.find("tr")
        if first_tr and isinstance(first_tr, Tag):
            cells = first_tr.find_all(["th", "td"])
            if any(c.name == "th" for c in cells if isinstance(c, Tag)):
                return self._cells_to_text(first_tr)

        return []

    def _extract_body_rows_bs4(
        self, table_tag: Tag, skip_first_if_no_thead: bool = False
    ) -> list[list[str]]:
        """Extract data rows from ``<tbody>`` or all ``<tr>`` elements.

        Args:
            table_tag: BeautifulSoup ``<table>`` Tag.
            skip_first_if_no_thead: When ``True``, skip the very first ``<tr>``
                (it was used as a header row).

        Returns:
            List of rows; each row is a list of cell text strings.
        """
        tbody = table_tag.find("tbody")
        source_tag: Tag = tbody if (tbody and isinstance(tbody, Tag)) else table_tag

        all_trs = source_tag.find_all("tr", recursive=False)
        if not all_trs and source_tag is not table_tag:
            all_trs = table_tag.find_all("tr")

        result: list[list[str]] = []
        for i, tr in enumerate(all_trs):
            if not isinstance(tr, Tag):
                continue
            if skip_first_if_no_thead and i == 0:
                continue
            result.append(self._cells_to_text(tr))

        return result

    def _cells_to_text(self, tr: Tag) -> list[str]:
        """Extract stripped text from each ``<td>`` / ``<th>`` in a row.

        Args:
            tr: A BeautifulSoup ``<tr>`` Tag.

        Returns:
            List of cell text strings.
        """
        return [
            cell.get_text(strip=True)
            for cell in tr.find_all(["td", "th"])
            if isinstance(cell, Tag)
        ]
