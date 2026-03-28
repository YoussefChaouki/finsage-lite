"""Retrieval quality metrics for the FinSage-Lite evaluation harness."""

from __future__ import annotations

import re

import numpy as np


def _normalize_text(text: str) -> str:
    """Normalize whitespace and case for robust text comparison.

    Args:
        text: Raw text string.

    Returns:
        Lowercased string with all whitespace runs collapsed to a single space.
    """
    return re.sub(r"\s+", " ", text.strip().lower())


def find_gold_rank(
    retrieved_contents: list[str],
    gold_evidence: str,
) -> int | None:
    """Return the 1-based rank of the first retrieved chunk containing gold evidence.

    Matching is attempted in this order:

    1. Normalized full-text substring match (gold ⊂ chunk).
    2. Normalized prefix match: first ≥ 50 characters of gold found within chunk.

    Args:
        retrieved_contents: Ordered chunk texts (rank 1 = index 0, best first).
        gold_evidence: Expected evidence passage from the evaluation dataset.

    Returns:
        1-based rank of the matching chunk, or ``None`` if not found in any chunk.
    """
    if not gold_evidence.strip():
        return None

    norm_gold = _normalize_text(gold_evidence)
    gold_prefix = norm_gold[:50]
    use_prefix = len(norm_gold) >= 50

    for rank, content in enumerate(retrieved_contents, start=1):
        norm_content = _normalize_text(content)
        if norm_gold in norm_content:
            return rank
        if use_prefix and gold_prefix in norm_content:
            return rank

    return None


def recall_at_k(
    retrieved_contents: list[str],
    gold_evidence: str,
    k: int = 5,
) -> float:
    """Compute Recall@k: 1.0 if gold evidence appears within the top-k chunks.

    Matching strategy: normalized substring match on chunk content (content_raw).

    Args:
        retrieved_contents: Ordered chunk texts (rank 1 = index 0, best first).
            Pass the textual content of each retrieved chunk, not chunk IDs.
        gold_evidence: Expected evidence passage from the evaluation dataset.
        k: Number of top results to consider.

    Returns:
        1.0 if gold evidence is found in the top-k results, 0.0 otherwise.
    """
    rank = find_gold_rank(retrieved_contents[:k], gold_evidence)
    return 1.0 if rank is not None else 0.0


def mrr(per_question_ranks: list[int | None]) -> float:
    """Compute Mean Reciprocal Rank (MRR).

    MRR = (1 / N) × Σ (1 / rank_i)

    where rank_i is the 1-based rank of the first relevant result for question i,
    and the contribution is 0 when no relevant result was found (rank_i is ``None``).

    Args:
        per_question_ranks: Per-question gold rank (1-based) or ``None`` if not found.

    Returns:
        MRR score in [0, 1]. Returns 0.0 for an empty list.
    """
    if not per_question_ranks:
        return 0.0
    reciprocal_sum = sum(1.0 / rank if rank is not None else 0.0 for rank in per_question_ranks)
    return reciprocal_sum / len(per_question_ranks)


def hit_rate_at_k(hits: list[bool]) -> float:
    """Compute Hit Rate: fraction of questions where the gold chunk was found.

    Args:
        hits: Per-question boolean indicating whether gold was found at rank ≤ k.

    Returns:
        Hit rate in [0, 1]. Returns 0.0 for an empty list.
    """
    if not hits:
        return 0.0
    return sum(hits) / len(hits)


def latency_stats(latencies_ms: list[float]) -> dict[str, float]:
    """Compute P50, P95, and P99 latency percentiles via ``numpy.percentile``.

    Args:
        latencies_ms: Per-question search latencies in milliseconds.

    Returns:
        Dict with keys ``p50``, ``p95``, ``p99`` (all in milliseconds).
        Returns all-zero dict for an empty list.
    """
    if not latencies_ms:
        return {"p50": 0.0, "p95": 0.0, "p99": 0.0}

    arr = np.array(latencies_ms, dtype=float)
    return {
        "p50": float(np.percentile(arr, 50)),
        "p95": float(np.percentile(arr, 95)),
        "p99": float(np.percentile(arr, 99)),
    }
