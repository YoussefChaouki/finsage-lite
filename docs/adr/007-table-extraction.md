# ADR-007: Table Extraction Strategy for 10-K Filings

## Status
Accepted

## Date
2026-03

## Context
SEC 10-K filings contain a large number of financial tables: income statements,
balance sheets, cash flow statements, segment breakdowns, and footnote schedules.
These tables are critical for quantitative queries ("What was Apple's FY2023 net
income?") but require a different extraction strategy than narrative text.

ADR-001 established that we parse iXBRL HTML rather than PDF. This ADR extends
that decision to define how tables inside the HTML are extracted, represented as
chunks, and indexed for both BM25 and dense retrieval.

## Decision

### 1. HTML over PDF for table extraction (extension of ADR-001)
We extract tables directly from the iXBRL HTML DOM using `pandas.read_html()`.
PDF-based alternatives (Camelot, Tabula) are explicitly excluded because:
- They require Ghostscript or a JVM runtime dependency.
- Visual PDF parsing produces alignment errors on multi-column financial tables.
- The iXBRL HTML already encodes cell structure in `<table>`, `<tr>`, `<td>` tags.

### 2. Fallback chain
Table extraction follows a three-step degradation chain:

```
pandas.read_html(<table_html>)
    └─ success → use parsed DataFrame
    └─ failure → BS4 custom parser (traverse <tr>/<td>, handle colspan/rowspan)
        └─ success → use reconstructed text table
        └─ failure → raw text extraction (strip tags, preserve whitespace)
```

The final fallback (raw text) ensures no table is silently dropped from the
corpus at the cost of losing structure.

### 3. Dual-content representation for TABLE chunks
Each extracted table is stored as a `Chunk` with `section = SectionType.TABLE`
and three distinct content representations:

| Field | Content | Used by |
|---|---|---|
| `content_raw` | Human-readable textual description: column headers + row summaries in prose | BM25 sparse retrieval |
| `metadata_["table_data"]` | JSON-serialized list of dicts (DataFrame.to_dict("records")) | LLM generation (Sprint 3) |
| `content_context` | `"[TABLE] " + content_raw` (short prefix + prose description) | Sentence-transformer embedding |

**Rationale for prose in `content_raw`**:
BM25 works on token overlap; JSON blobs and numeric cells do not tokenize
meaningfully. Converting the table to a prose description ("Revenue for fiscal
year 2023 was 394 billion dollars…") ensures keyword search can surface tables
on relevant queries.

**Rationale for JSON in `metadata_["table_data"]`**:
The LLM generation layer (Sprint 3) needs structured data to produce accurate
cited figures. JSON preserves exact numeric values and column labels, avoiding
the rounding/paraphrase introduced by prose descriptions.

### 4. Layout table filtering
Not all `<table>` elements in an iXBRL HTML document contain financial data.
Many are used for page layout (navigation bars, header blocks, footnote
formatting). These must be filtered before extraction.

**Heuristic: fewer than 2 columns with numeric content → skip**.

A column is considered "numeric" if ≥ 50 % of its non-empty cells match
the regex `r'[\d,\.\-\(\)$%]+'`. Tables where fewer than 2 columns pass this
threshold are classified as layout tables and excluded from the TABLE chunk
pipeline. They may still contribute to surrounding narrative chunks.

## Consequences

### Positive
- Financial tables become searchable via both BM25 (prose description) and
  dense retrieval (semantic embedding), closing a major gap in Sprint 2 recall.
- JSON `table_data` in metadata enables the LLM to cite exact figures without
  hallucinating values from paraphrased prose.
- The three-level fallback chain prevents silent data loss on malformed tables.
- Layout table filtering reduces noise chunks that degrade retrieval precision.

### Negative
- Prose generation for `content_raw` adds a transformation step that may
  introduce paraphrase errors for very large tables (100+ rows); such tables
  should be split into sub-tables before prose generation.
- `metadata_["table_data"]` can be large (several KB per table); this increases
  DB storage per chunk and may require a size cap in the chunker.
- The layout heuristic (< 2 numeric columns) is imperfect: some qualitative
  tables (e.g., risk factor matrices) will be incorrectly excluded. Tuning
  may be needed post Sprint 3 evaluation.

## Alternatives Considered

| Alternative | Rejected reason |
|---|---|
| Store raw HTML in `content_raw` | BM25 cannot tokenize HTML tags; search quality collapses |
| Embed JSON directly | JSON is not natural language; sentence-transformers produce poor vectors for structured data |
| Single content field for all chunk types | Loses the BM25/dense distinction; dual-field design is already established for narrative chunks |
| Camelot / Tabula for table extraction | Require non-Python system dependencies; ADR-001 explicitly excludes them |

## References
- ADR-001: HTML Parsing Over PDF Extraction
- ADR-003: BM25 In-Memory Index
- [iXBRL specification](https://www.xbrl.org/guidance/ixbrl-tagging-of-financial-statements/)
- `pandas.read_html` documentation
