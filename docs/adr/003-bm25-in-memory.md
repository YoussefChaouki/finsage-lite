# ADR-003: In-Memory BM25 Over Elasticsearch

## Status
Accepted

## Date
2026-02

## Context
Hybrid retrieval requires a sparse (lexical) search component alongside
dense (embedding) search. Options: Elasticsearch/OpenSearch (full-text
search engine), rank_bm25 (Python in-memory BM25 library).

## Decision
Use rank_bm25 for in-memory BM25 indexing and scoring.

## Rationale
- **Simplicity**: No additional infrastructure. BM25 index built at
  startup from database contents, held in application memory
- **Latency**: In-memory scoring achieves P50 ~1ms vs Elasticsearch
  network round-trip of ~5-20ms
- **Corpus size**: At ~1k chunks per filing and ~5 filings target,
  the full corpus (~5k chunks) fits comfortably in memory (~10MB)
- **Zero ops burden**: No Elasticsearch cluster to configure, monitor,
  or secure

## Consequences
### Positive
- Docker stack stays minimal (API + PostgreSQL only for core search)
- Benchmark shows P99 < 2ms for sparse search
- No network hop — scoring happens in-process

### Negative
- Index must be rebuilt after ingestion (manual POST /rebuild-index)
- Not horizontally scalable — each API instance holds its own index
- No persistent BM25 index — cold start requires loading all chunks from DB
- No advanced text analysis (stemming, synonyms) without custom implementation

## Scaling Path
For multi-instance deployment: add Redis-backed BM25 or switch to Elasticsearch.
For advanced text analysis: integrate NLTK stemmer in tokenize_for_bm25().
