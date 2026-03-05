# ADR-001: HTML Parsing Over PDF Extraction

## Status
Accepted

## Context
SEC EDGAR provides 10-K filings in two formats: PDF and iXBRL HTML.
Most RAG tutorials use PDF parsers (PyPDF, Camelot, LlamaParse) to extract
content. We needed to choose which format to parse for our ingestion pipeline.

## Decision
We parse the iXBRL HTML filing directly using BeautifulSoup + lxml,
instead of downloading and parsing the PDF version.

## Rationale
- **Structured metadata**: iXBRL HTML contains `dei:` tags with company name,
  CIK, fiscal year — extractable without heuristics
- **Section detection**: Bold `<span>` elements with `font-weight:700` reliably
  mark section headings (Item 1, Item 1A, etc.)
- **Table preservation**: HTML tables retain structure (`<tr>`, `<td>`),
  enabling `pandas.read_html()` extraction. PDF tables require error-prone
  visual parsing
- **No external dependencies**: No Camelot (requires Ghostscript), no LlamaParse
  (API dependency). Only BeautifulSoup + lxml (pure Python)
- **Smaller footprint**: HTML files are ~2-5MB vs PDF files at 10-15MB

## Consequences
### Positive
- Cleaner section boundaries (DOM traversal vs regex on flat text)
- Reliable metadata extraction from iXBRL tags
- Table extraction becomes straightforward (Sprint 3)
- Faster processing — no PDF rendering needed

### Negative
- Tightly coupled to SEC EDGAR's iXBRL format — other document sources
  would need a separate parser
- Some older filings (pre-2020) may use non-standard HTML structures
- Text cleanup requires handling iXBRL noise (hidden divs, inline XBRL tags)
