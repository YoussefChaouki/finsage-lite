# Sprint 3 Results — Table Extraction

## Table Extraction — AAPL FY2024

Analysis run against `data/filings/0000320193_0000320193-24-000123.html` (Apple FY2024 10-K).

### TABLE chunk counts by section

| Section | TABLE chunks |
|---|---|
| ITEM_1 (Business) | 0 |
| ITEM_1A (Risk Factors) | 0 |
| ITEM_7 (MD&A) | 6 |
| ITEM_7A (Market Risk) | 1 |
| ITEM_8 (Financial Statements) | 33 |
| **Total** | **40** |

### Pipeline coverage

- 40 TABLE chunks produced alongside ~350 TEXT chunks per full ingestion
- All 40 tables survived the `detect_tables()` layout-filter (≥2 numeric columns)
- `to_description()` generates plain-text representations stored in `content_raw`
- `to_json_str()` preserves structured data in `metadata["table_data"]`

---

## Example: Net Sales by Segment (ITEM_7)

```
Financial table: Table 0 | Apple Inc. 10-K FY2024 | Management Discussion and Analysis
Columns: 0, 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12, 13, 14, 15, 16, 17, 18, 19, 20, 21, 22, 23, 24, 25, 26, 27, 28, 29
Americas: Americas, $, 167045.0, ..., 3, %
Europe: Europe, 101328, ..., 7, %
Greater China: Greater China, 66952, ..., (8), %
Japan: Japan, 25052, ..., 3, %
Rest of Asia Pacific: Rest of Asia Pacific, 30658, ..., 4, %
Total net sales: Total net sales, $, 391035.0, ..., 2, %
```

This table covers Apple's FY2024 regional net sales ($391B total) alongside YoY % changes.

---

## Limitations Observed

### 1. Numeric column headers (main limitation)
EDGAR iXBRL HTML tables for AAPL use `<td>` for all cells with no `<thead>/<th>` elements.
`pandas.read_html()` fallback assigns numeric headers (`0`, `1`, `2`, ...) instead of
semantic names like `"Region"`, `"FY2024"`, `"FY2023"`. All 40 tables are affected.

**Impact**: `to_description()` outputs `Columns: 0, 1, 2, ...` rather than human-readable
column names. The row labels (first column) are preserved correctly.

**Fix path**: Pre-process the raw HTML to transpose de-merged cells and detect the header
row heuristically before calling `pandas.read_html()`.

### 2. Colspan / merged header cells
Multi-year comparison tables (e.g. "FY2024 / Change / FY2023 / Change / FY2022") span
across merged cells. pandas and BS4 both flatten these into repeated values with `.0` suffixes
(e.g. `2024.0, 2024.0`). Cell deduplication would improve description quality.

### 3. Table title attribution
No `<caption>` elements found in the AAPL 10-K. All 40 tables receive fallback titles
(`Table 0`, `Table 1`, ...). Upstream title extraction from the preceding paragraph or
XBRL label would be needed for meaningful titles.

### 4. Index/TOC tables in ITEM_8
The first table in ITEM_8 is an index of financial statements (page references), not
financial data. It passes the numeric-column filter because page numbers count as numerics.
A minimum meaningful row count (≥5) or content-type check could filter these out.

### 5. ITEM_1 / ITEM_1A: zero tables
Business and Risk Factors sections contain no financial tables in AAPL's filing format.
All quantitative data in those sections is embedded inline in text paragraphs.
