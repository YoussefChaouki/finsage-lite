# ADR-006: Section-Aware Chunking with Dual Content Strategy

## Status
Accepted

## Date
2026-02

## Context
10-K filings contain distinct sections (Business, Risk Factors, MD&A,
Financial Statements) with different content types and retrieval needs.
Naive chunking across section boundaries loses context about which
section a passage belongs to.

## Decision
Implement section-aware chunking that:
1. Chunks within section boundaries (never across)
2. Produces dual content per chunk: `content_raw` and `content_context`
3. Enriches each chunk with section metadata in JSONB

## Rationale
- **Section boundaries preserve context**: A risk factor about "supply
  chain disruption" means something different in Item 1A (risk) vs
  Item 7 (management's response)
- **Dual content strategy**:
  - `content_raw`: plain text, used for BM25 (no prefix noise)
  - `content_context`: prefixed with "[Company | 10-K FYxxxx | Section]",
    used for embedding. The prefix steers the embedding model toward
    the correct semantic space
- **Metadata enables filtering**: Section type stored in both the enum
  column (fast SQL filter) and JSONB (flexible future queries)
- **Chunk size 220 tokens**: Leaves ~35 token headroom for the contextual
  prefix within MiniLM's 256-token window

## Consequences
### Positive
- Section-filtered search (e.g., "only Risk Factors") is a SQL WHERE clause
- Embedding quality improved by contextual prefix (company + year + section)
- BM25 not polluted by repeated prefixes across chunks

### Negative
- Two content fields per chunk doubles text storage (~2x for text columns)
- Short sections may produce very few chunks (reduced retrieval diversity)
- Chunk size tuned for MiniLM-L6-v2 — switching embedding model requires
  re-evaluating this parameter
