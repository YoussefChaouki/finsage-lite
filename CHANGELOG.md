# Changelog

All notable changes to FinSage-Lite are documented in this file.

Format: [Keep a Changelog](https://keepachangelog.com/en/1.0.0/)
Versioning: [Semantic Versioning](https://semver.org/spec/v2.0.0.html)

---

## [1.0.0] — 2026-04 — Production Release

### Summary
First production-ready release of FinSage-Lite. Complete SEC 10-K RAG
pipeline with hybrid retrieval (BM25 + pgvector + RRF), HyDE query
expansion, table extraction, FinanceBench evaluation harness, and a
professional React terminal-style frontend.

### Highlights
- Hybrid retrieval achieving Recall@5 ≥ 85% on FinanceBench subset
- Section-aware chunking with dual-content strategy (220 token chunks)
- 40+ financial tables extracted per filing via 3-step fallback chain
- React frontend with bidirectional citation highlighting
- 86+ unit tests, CI/CD via GitHub Actions
- Full Docker Compose deployment (API + Frontend + PostgreSQL/pgvector)

---

## [0.6.0] — 2026-04 — Sprint 6 : Polish & Documentation

### Added
- Production-grade README with badges, screenshots, evaluation metrics, and architecture diagram
- CHANGELOG.md
- `docs/sprints/SPRINT_RESULTS.md` — consolidated sprint retrospective
- `docs/architecture/frontend-overview.md` — React frontend architecture reference
- `docs/screenshots/` directory with contributor guide

### Changed
- Removed `streamlit_app/` (replaced by React frontend in v0.5.0)
- `pyproject.toml`: removed `streamlit>=1.31.0` dependency
- ADR index (`docs/adr/README.md`) updated with ADR-007 and ADR-008
- Date field added to all ADR files (001–008)

### Fixed
- README placeholder screenshots replaced with actual Sprint 5 captures
- Frontend TypeScript errors: unused `Database` import, Framer Motion `ease` type
- Integration test `test_ingest_invalid_ticker` timeout raised to 60 s

---

## [0.5.0] — 2026-04 — Sprint 5 : React Frontend

### Added
- React 19 + Vite + Tailwind CSS + shadcn/ui frontend (replaces Streamlit)
- `SearchPage` with typewriter effect, citation highlighting, bidirectional source-card hover
- `BrowsePage` with filing selector, section navigation, and inline content reader
- `DocumentsPage` with filing grid, stats strip, ingest form, and progress stepper
- Zustand global state (`appStore`) for search filters and mode
- TanStack Query v5 for server state (`useSearch`, `useDocuments`, `useBrowse`, `useIngest`)
- Docker multi-stage build: dev (Vite HMR) + production (nginx static)
- Keyboard shortcuts: `⌘K` focus search, `⌘/` help, `Esc` clear
- `RebuildIndexButton` component exposing `POST /api/v1/search/rebuild-index`

---

## [0.4.0] — 2026-03 — Sprint 4 : Evaluation & Benchmarks

### Added
- `EvalHarness` with 4 retrieval configurations (dense / sparse / hybrid / hybrid+HyDE)
- `FinanceBenchLoader` consuming PatronusAI/financebench dataset
- F1 token-level generation metrics + optional RAGAS integration
- `AblationRunner` for RRF k and HyDE category ablations
- `ReportGenerator` producing auto-generated Markdown reports from JSON results
- ADR-008: FinanceBench corpus scope decision
- `make evaluate` / `make ablation` / `make evaluate-report` Makefile targets
- Evaluation corpus: PEP FY2023, AMCR FY2023, JNJ FY2022, MMM FY2023

---

## [0.3.0] — 2026-03 — Sprint 3 : Table Extraction

### Added
- `TableParser` with 3-step fallback chain: pandas HTML → BeautifulSoup4 → raw text
- Layout table filtering heuristic (< 2 numeric columns → skip)
- Dual-content strategy for `TABLE` chunks: JSON for dense, human-readable for sparse (ADR-007)
- 40 TABLE chunks extracted from AAPL FY2024 10-K
- Integration tests for the full table extraction pipeline

---

## [0.2.0] — 2026-02 — Sprint 2 : Hybrid Retrieval & HyDE

### Added
- `BM25Service`: rank_bm25 in-memory index, `tokenize_for_bm25` with financial term preservation
- `RetrievalService`: RRF fusion with k=60, scores normalised to [0, 1] (ADR-004)
- `HyDEService`: hypothetical document expansion with analytical query detection (ADR-005)
- `GenerationService`: Ollama/Mistral cited answer synthesis with graceful degradation
- `POST /api/v1/search` — dense / sparse / hybrid / HyDE modes
- `POST /api/v1/search/rebuild-index` — in-memory BM25 rebuild
- `GET /api/v1/search/health` — BM25 index size + Ollama availability
- Search latency benchmarks: dense P50=10 ms, sparse P50=1 ms, hybrid P50=12 ms

---

## [0.1.0] — 2026-02 — Sprint 1 : SEC EDGAR Ingestion

### Added
- Full project scaffold following CITADEL RAG patterns
- `EdgarClient`: async CIK resolution, 10-K filing listing, HTML download with local cache
- `FilingParser`: iXBRL HTML → section-aware extraction (Item 1, 1A, 7, 7A, 8)
- `SectionChunker`: 220-token overlapping windows, dual-content fields (ADR-006)
- `EmbeddingService`: all-MiniLM-L6-v2 (384-dim), pgvector IVFFlat cosine index
- `IngestionService`: end-to-end EDGAR → parse → chunk → embed → store pipeline
- Alembic migrations for `documents` and `chunks` tables
- Docker Compose: FastAPI + PostgreSQL 16 + pgvector + Ollama
- GitHub Actions CI: lint + type-check + unit tests
