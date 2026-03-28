# Sprint 4 Results — Evaluation Harness & Benchmarks

## What was built

Sprint 4 delivers a complete, self-contained evaluation framework for the
FinSage-Lite RAG pipeline, covering retrieval metrics, generation quality,
ablation studies, and automated Markdown report generation.

### Evaluation modules

| Module | Description |
|---|---|
| `evaluation/schemas.py` | `EvalQuestion` + `EvalConfig` (Pydantic v2) |
| `evaluation/datasets/financebench.py` | `FinanceBenchLoader` — HuggingFace loader with filtering |
| `evaluation/metrics_retrieval.py` | Recall@k, MRR, HitRate@k, latency p50/p95/p99 |
| `evaluation/metrics_generation.py` | F1 token-level (default) + RAGAS wrapper (optional) |
| `evaluation/harness.py` | `EvalHarness` — 4-config runner, JSON serialization |
| `evaluation/ablation.py` | `AblationRunner` — RRF k sweep + HyDE per-category |
| `evaluation/report_generator.py` | `ReportGenerator` — auto-generates Markdown report |

---

## Benchmark Corpus — FinanceBench Subset

Selected per ADR-008 (criteria: max questions, 1 filing/company, ≥3 companies).

| Company | Ticker | Fiscal Year | Questions |
|---------|--------|-------------|-----------|
| PepsiCo | PEP | FY2023 | 5 |
| Amcor | AMCR | FY2023 | 7 |
| Johnson & Johnson | JNJ | FY2022 | 5 |
| 3M | MMM | FY2023 | 3 |
| **Total** | | | **20 / 150 (13.3%)** |

Category distribution (FinanceBench): `metrics-generated` · `domain-relevant` · `novel-generated` (50 each in full dataset).

---

## Evaluation Configurations

| Config | Mode | RRF k | HyDE |
|---|---|---|---|
| `dense_only` | dense | — | ✗ |
| `bm25_only` | bm25 | — | ✗ |
| `hybrid` | hybrid | 60 | ✗ |
| `hybrid_hyde` | hybrid | 60 | ✓ |

---

## Retrieval Metrics (run `make evaluate` to populate)

> Requires: `make docker-up` + `make seed` with PEP/AMCR/JNJ/MMM filings ingested.

| Config | Recall@1 | Recall@3 | Recall@5 | MRR | HitRate@1 | p50 (ms) | p95 (ms) |
|---|---|---|---|---|---|---|---|
| dense_only | — | — | — | — | — | — | — |
| bm25_only | — | — | — | — | — | — | — |
| hybrid | — | — | — | — | — | — | — |
| hybrid_hyde | — | — | — | — | — | — | — |

**Target**: Recall@5 ≥ 85% on best config.

---

## RRF k Ablation (run `make ablation` to populate)

| k | Recall@5 | MRR | Δ vs k=60 |
|---|---|---|---|
| 10 | — | — | — |
| 30 | — | — | — |
| 60 | — | — | — |
| 100 | — | — | — |

---

## HyDE Impact (run `make ablation` to populate)

| Category | Hybrid (no HyDE) | Hybrid + HyDE | Δ |
|---|---|---|---|
| global | — | — | — |

---

## Generation Quality (run `make evaluate` with Ollama to populate)

| Config | F1 Score | Answer Correctness | Faithfulness |
|---|---|---|---|
| hybrid_hyde | — | — | — |

Enable RAGAS: `make evaluate-with-ragas` (requires Ollama + `mistral` model).

---

## Test Coverage

379 tests passing — `make check` green.

| Suite | Tests | Status |
|---|---|---|
| Unit (src/) | 274 | ✅ |
| Evaluation (harness, metrics, loader, report) | 73 | ✅ |
| Integration (E2E, table extraction) | 32 | ✅ |

---

## How to reproduce

```bash
# 1. Start the stack
make docker-up && make migrate

# 2. Ingest benchmark filings (PEP FY2023, AMCR FY2023, JNJ FY2022, MMM FY2023)
python scripts/seed_demo_data.py  # or ingest via POST /api/v1/documents

# 3. Run full evaluation
make evaluate          # 4 configs → evaluation/results/eval_*.json
make ablation          # RRF k sweep + HyDE study → evaluation/results/
make evaluate-report   # → evaluation/reports/report_YYYYMMDD_HHMMSS.md

# 4. Optional: RAGAS generation metrics
make evaluate-with-ragas
```
