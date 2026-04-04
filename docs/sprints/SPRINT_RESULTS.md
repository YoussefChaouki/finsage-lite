# FinSage-Lite — Sprint Results

Consolidated retrospective for all six sprints. Metrics and decisions are final
as of v0.6.0.

---

## Sprint 1 — SEC EDGAR Ingestion (v0.1.0, 2026-02)

**Objective:** Build the full ingestion pipeline from SEC EDGAR to pgvector.

**Delivered:**
- `EdgarClient` resolves ticker → CIK, lists 10-K filings, downloads iXBRL HTML
- `FilingParser` extracts 5 named sections (Item 1, 1A, 7, 7A, 8) from raw HTML
- `SectionChunker` produces overlapping 220-token windows with dual content fields
- `EmbeddingService` stores 384-dim MiniLM vectors in pgvector (IVFFlat cosine index)
- Docker Compose stack + Alembic migrations + GitHub Actions CI

**Key metrics:**
- AAPL FY2024: 164 chunks ingested end-to-end in < 60 s
- CI: ruff + mypy strict + unit tests green on first push

**Notable decisions:**
- ADR-001: HTML over PDF — iXBRL HTML preserves structure; PDF parsers lose table layout
- ADR-006: Dual-content chunking — `content_raw` for BM25 readability, `content_context` prefixed for dense embedding quality

---

## Sprint 2 — Hybrid Retrieval & HyDE (v0.2.0, 2026-02)

**Objective:** Add BM25 sparse retrieval, RRF fusion, HyDE query expansion, and the search endpoint.

**Delivered:**
- `BM25Service` in-memory index with financial-term-aware tokeniser (no stemming)
- `RetrievalService` orchestrating dense + sparse + RRF; scores normalised to [0, 1]
- `HyDEService` with analytical query heuristic; graceful degradation if Ollama unavailable
- `GenerationService` producing cited answers via Ollama/Mistral
- `POST /api/v1/search` supporting dense / sparse / hybrid / HyDE modes
- Search latency benchmark script (`scripts/benchmark_search.py`)

**Key metrics:**
- dense P50 = 10 ms, sparse P50 = 1 ms, hybrid P50 = 12 ms (164 chunks, 20 queries)
- 291 unit tests, all green

**Notable decisions:**
- ADR-003: In-memory BM25 — eliminates Elasticsearch operational overhead; rebuild < 1 s at current corpus size
- ADR-004: RRF over linear combination — avoids incompatible score scales between cosine and BM25
- ADR-005: HyDE on analytical queries only — factual queries degrade with hypothetical expansion

---

## Sprint 3 — Table Extraction (v0.3.0, 2026-03)

**Objective:** Extract financial tables from 10-K HTML and make them searchable.

**Delivered:**
- `TableParser` with 3-step fallback: pandas `read_html` → BS4 manual parse → raw text preservation
- Layout-table filter: tables with < 2 numeric columns classified as decorative and skipped
- TABLE chunks stored with dual content: JSON representation for dense embedding, human-readable description for BM25
- 40 TABLE chunks extracted from AAPL FY2024 10-K (income statement, balance sheet, segment data)
- Integration tests covering the full table extraction path

**Key metrics:**
- 40 TABLE chunks / 164 total chunks in AAPL FY2024 (24%)
- Fallback chain: ~95% of tables parsed by pandas, remainder by BS4

**Notable decisions:**
- ADR-007: Dual-content for tables — JSON string optimises dense recall; natural-language description improves BM25 keyword match

---

## Sprint 4 — Evaluation & Benchmarks (v0.4.0, 2026-03)

**Objective:** Measure retrieval quality against a real financial QA benchmark.

**Delivered:**
- `EvalHarness` running 4 retrieval configurations: `dense_only`, `bm25_only`, `hybrid`, `hybrid_hyde`
- `FinanceBenchLoader` pulling PatronusAI/financebench from HuggingFace
- F1 token-level scoring + optional RAGAS metrics
- `AblationRunner`: RRF k sweep (20–100) and HyDE category ablation
- `ReportGenerator` writing Markdown + JSON reports to `evaluation/reports/`

**Key metrics:**

| Config | Recall@5 | MRR |
|--------|----------|-----|
| dense_only | 72% | 0.61 |
| bm25_only | 58% | 0.49 |
| hybrid | 81% | 0.72 |
| hybrid_hyde | **87%** | **0.78** |

Corpus: PEP FY2023, AMCR FY2023, JNJ FY2022, MMM FY2023 (PatronusAI/financebench subset).

**Notable decisions:**
- ADR-008: FinanceBench corpus — industry-standard benchmark with analyst-verified answers; enables reproducible comparison with published RAG systems

---

## Sprint 5 — React Frontend (v0.5.0, 2026-04)

**Objective:** Replace the Streamlit prototype with a production-grade React SPA.

**Delivered:**
- `SearchPage`: query bar, mode selector, HyDE toggle, animated source cards, cited answer panel
- `BrowsePage`: filing selector, section navigation, inline content reader
- `DocumentsPage`: filing grid with stats strip, ingest form, 4-step progress indicator
- Docker multi-stage build: Vite dev (HMR) + nginx production static serving
- Keyboard shortcuts: `⌘K` focus, `⌘/` help, `Esc` clear
- TypeScript strict mode, Framer Motion animations, shadcn/ui component library

**Key metrics:**
- 5 filings ingested in demo dataset (1 210 chunks, 3 companies)
- Frontend TypeScript: 0 errors (strict mode)
- Lighthouse performance score: > 90 on production build

**Notable decisions:**
- Zustand for ephemeral UI state (filters reset on refresh — intentional)
- TanStack Query for server cache with 30 s stale time on document lists
- nginx for production serving — eliminates Node.js runtime dependency in prod container

---

## Sprint 6 — Polish & Documentation (v0.6.0, 2026-04)

**Objective:** Portfolio-ready housekeeping: remove dead code, complete documentation.

**Delivered:**
- `streamlit_app/` deleted; `streamlit` removed from `pyproject.toml`
- Production-grade README: badges, screenshots, evaluation table, architecture diagram, 8 ADRs
- `CHANGELOG.md` (this file's sibling) in Keep a Changelog format
- `docs/architecture/frontend-overview.md` — component tree, state management, routing
- `docs/screenshots/` directory with contributor guide
- ADR-007 and ADR-008 added to `docs/adr/README.md` index
- Date field added to all ADR files
- Frontend TS errors fixed (unused import, Framer Motion `ease` type)
- Integration test timeout corrected (`test_ingest_invalid_ticker`: 30 s → 60 s)

**Key metrics:**
- `make check` fully green (ruff + mypy strict + 291 unit tests + frontend tsc)
- 0 TODO / FIXME in `src/` or `evaluation/`
- 0 dead `.py` files
