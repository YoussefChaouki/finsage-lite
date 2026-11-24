# FinSage-Lite — Search Latency Benchmarks

**Date**: 2026-03-03 21:40 UTC
**Environment**: Darwin, Docker, pgvector
**Dataset**: 164 chunks (AAPL FY2024)
**Runs per query**: 3

## Results

| Mode    | P50 (ms) | P95 (ms) | P99 (ms) | Avg results   |
|---------|----------|----------|----------|---------------|
| dense   |     10.1 |     31.6 |     36.7 |           5.0 |
| sparse  |      1.0 |      1.3 |      1.4 |           5.0 |
| hybrid  |     11.9 |     25.0 |     30.8 |           5.0 |

## Targets

| Mode    | Target   | Status |
|---------|----------|--------|
| dense   | < 1000ms | ✅     |
| sparse  | < 500ms  | ✅     |
| hybrid  | < 2000ms | ✅     |

## Notes

- BM25 index: in-memory, rebuilt at startup
- Dense: pgvector ivfflat cosine, lists=100
- HyDE is not included in these benchmarks (it depends on Ollama)
- Queries tested: 20 (3 runs each)

## Details per mode

### Dense
- Avg: 13.6 ms
- Errors: 0/60

### Sparse
- Avg: 1.1 ms
- Errors: 0/60

### Hybrid
- Avg: 13.8 ms
- Errors: 0/60

