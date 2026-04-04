# ADR-004: Reciprocal Rank Fusion Over Linear Score Combination

## Status
Accepted

## Date
2026-03

## Context
Hybrid retrieval requires fusing ranked lists from dense (cosine similarity)
and sparse (BM25 score) retrieval. The two scoring scales are incomparable:
cosine similarity ∈ [0,1] while BM25 scores are unbounded positive reals.

## Decision
Use Reciprocal Rank Fusion (RRF) with k=60 to merge dense and sparse
ranked lists.

## Rationale
- **Score-agnostic**: RRF operates on rank positions, not raw scores.
  No normalization needed between cosine similarity and BM25 scores
- **Parameter-free in practice**: k=60 is the original paper's default
  and works well across domains without tuning
- **Simple implementation**: ~30 lines of code, easy to test and debug
- **Industry standard**: Used by Elasticsearch, Azure AI Search, and
  most production hybrid search systems

## Consequences
### Positive
- No need to calibrate or normalize BM25 and cosine scores
- Deterministic — same inputs always produce same output
- Individual dense and sparse scores preserved in response for debugging

### Negative
- Ignores magnitude of scores (a very high BM25 match is treated same as
  slightly-above-average if rank position is identical)
- k=60 may not be optimal for financial domain (could be tuned on eval set)
- Equal weighting of dense and sparse — no way to favor one over the other
  without modifying the formula

## Alternatives Considered
- **Linear combination** (α·dense + (1-α)·sparse): Requires score normalization
  and α tuning per query type. More knobs, more fragile.
- **Convex combination with learned weights**: Requires training data.
  Overkill for the current corpus size.
