"""
Integration Tests — Search Latency Smoke Tests

Verifies that each search mode responds within acceptable latency bounds
when the Docker stack is running (make docker-up).

These are *smoke tests*, not statistical benchmarks.  For P50/P95/P99
measurements use: make benchmark

Run with: make test-int
"""

from __future__ import annotations

import time

import httpx
import pytest

BASE_SEARCH = "/api/v1/search"

# Latency ceilings for pure retrieval (generate=False).
# LLM generation is excluded — it is hardware-dependent and tested separately.
# Targets: dense ~0.5s (embedding + pgvector), sparse ~0.3s (BM25 in-memory),
# hybrid ~0.8s (both + RRF fusion).  Ceilings are 4× targets to allow headroom.
LATENCY_LIMITS: dict[str, float] = {
    "dense": 2.0,
    "sparse": 1.0,
    "hybrid": 3.0,
}

SMOKE_QUERY = "What is Apple's total revenue?"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _post_search(client: httpx.Client, mode: str, query: str) -> tuple[int, float]:
    """Return (status_code, elapsed_seconds) for a retrieval-only request.

    ``generate=False`` skips Ollama so we measure pure retrieval latency
    instead of mixing hardware-dependent LLM time into the assertion.
    """
    t0 = time.perf_counter()
    resp = client.post(
        BASE_SEARCH,
        json={"query": query, "search_mode": mode, "top_k": 5, "generate": False},
        timeout=10.0,
    )
    elapsed = time.perf_counter() - t0
    return resp.status_code, elapsed


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.integration
def test_dense_search_latency(api_client: httpx.Client) -> None:
    """Dense search must respond within latency ceiling."""
    status, elapsed = _post_search(api_client, "dense", SMOKE_QUERY)
    assert status == 200
    assert elapsed < LATENCY_LIMITS["dense"], (
        f"Dense search too slow: {elapsed:.2f}s > {LATENCY_LIMITS['dense']}s"
    )


@pytest.mark.integration
def test_sparse_search_latency(api_client: httpx.Client) -> None:
    """Sparse (BM25) search must respond within latency ceiling."""
    status, elapsed = _post_search(api_client, "sparse", SMOKE_QUERY)
    assert status == 200
    assert elapsed < LATENCY_LIMITS["sparse"], (
        f"Sparse search too slow: {elapsed:.2f}s > {LATENCY_LIMITS['sparse']}s"
    )


@pytest.mark.integration
def test_hybrid_search_latency(api_client: httpx.Client) -> None:
    """Hybrid search (dense + sparse + RRF) must respond within latency ceiling."""
    status, elapsed = _post_search(api_client, "hybrid", SMOKE_QUERY)
    assert status == 200
    assert elapsed < LATENCY_LIMITS["hybrid"], (
        f"Hybrid search too slow: {elapsed:.2f}s > {LATENCY_LIMITS['hybrid']}s"
    )


@pytest.mark.integration
def test_hybrid_not_slower_than_3x_dense(api_client: httpx.Client) -> None:
    """Hybrid search should not be more than 3× slower than dense alone."""
    _, dense_elapsed = _post_search(api_client, "dense", SMOKE_QUERY)
    _, hybrid_elapsed = _post_search(api_client, "hybrid", SMOKE_QUERY)

    # Allow some variance — hybrid adds BM25 + RRF overhead
    assert hybrid_elapsed < dense_elapsed * 3 + 0.5, (
        f"Hybrid ({hybrid_elapsed:.2f}s) suspiciously slower than 3x dense ({dense_elapsed:.2f}s)"
    )
