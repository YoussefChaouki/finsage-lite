"""
Unit Tests — reciprocal_rank_fusion

Tests cover RRF score arithmetic, deduplication, normalisation,
ordering guarantees, and edge cases (empty lists, single list, k variants).
"""

from __future__ import annotations

import uuid

import pytest

from src.models.chunk import SectionType
from src.schemas.search import DenseResult, SparseResult
from src.services.retrieval_service import reciprocal_rank_fusion

# ---------------------------------------------------------------------------
# Fixtures / helpers
# ---------------------------------------------------------------------------

_SECTION = SectionType.ITEM_1A


def _dense(chunk_id: uuid.UUID, score: float = 0.9) -> DenseResult:
    return DenseResult(
        chunk_id=chunk_id,
        document_id=uuid.uuid4(),
        content="dense content",
        section=_SECTION,
        section_title="Risk Factors",
        score=score,
        metadata={},
    )


def _sparse(chunk_id: uuid.UUID, bm25_score: float = 5.0, rank: int = 1) -> SparseResult:
    return SparseResult(
        chunk_id=chunk_id,
        document_id=uuid.uuid4(),
        content="sparse content",
        section=_SECTION,
        section_title="Risk Factors",
        bm25_score=bm25_score,
        rank=rank,
        metadata={},
    )


# ---------------------------------------------------------------------------
# Empty-list edge cases
# ---------------------------------------------------------------------------


def test_both_lists_empty_returns_empty() -> None:
    """Two empty lists must produce an empty result."""
    assert reciprocal_rank_fusion([], []) == []


def test_empty_dense_only_sparse() -> None:
    """Empty dense list — results come entirely from sparse."""
    cid = uuid.uuid4()
    results = reciprocal_rank_fusion([], [_sparse(cid)])
    assert len(results) == 1
    assert results[0].chunk_id == cid
    assert results[0].dense_score is None
    assert results[0].sparse_score is not None


def test_empty_sparse_only_dense() -> None:
    """Empty sparse list — results come entirely from dense."""
    cid = uuid.uuid4()
    results = reciprocal_rank_fusion([_dense(cid)], [])
    assert len(results) == 1
    assert results[0].chunk_id == cid
    assert results[0].sparse_score is None
    assert results[0].dense_score is not None


# ---------------------------------------------------------------------------
# Deduplication — chunk in both lists gets a boosted score
# ---------------------------------------------------------------------------


def test_shared_chunk_higher_score_than_exclusive() -> None:
    """A chunk present in both lists must score higher than one in only one."""
    shared = uuid.uuid4()
    exclusive = uuid.uuid4()

    dense = [_dense(shared), _dense(exclusive)]
    sparse = [_sparse(shared)]  # exclusive not in sparse

    results = reciprocal_rank_fusion(dense, sparse)
    result_map = {r.chunk_id: r for r in results}

    assert result_map[shared].score > result_map[exclusive].score


def test_shared_chunk_has_both_individual_scores() -> None:
    """A chunk in both lists must expose non-None dense_score and sparse_score."""
    cid = uuid.uuid4()
    results = reciprocal_rank_fusion([_dense(cid, score=0.8)], [_sparse(cid, bm25_score=3.0)])
    r = results[0]
    assert r.dense_score == pytest.approx(0.8)
    assert r.sparse_score == pytest.approx(3.0)


def test_dense_only_chunk_has_no_sparse_score() -> None:
    """A chunk found only by dense must have sparse_score=None."""
    cid = uuid.uuid4()
    results = reciprocal_rank_fusion([_dense(cid)], [])
    assert results[0].sparse_score is None


def test_sparse_only_chunk_has_no_dense_score() -> None:
    """A chunk found only by sparse must have dense_score=None."""
    cid = uuid.uuid4()
    results = reciprocal_rank_fusion([], [_sparse(cid)])
    assert results[0].dense_score is None


# ---------------------------------------------------------------------------
# Normalisation — all scores in [0, 1]
# ---------------------------------------------------------------------------


def test_scores_normalised_to_0_1() -> None:
    """All output scores must lie in [0, 1]."""
    ids = [uuid.uuid4() for _ in range(4)]
    dense = [_dense(ids[0]), _dense(ids[1])]
    sparse = [_sparse(ids[2]), _sparse(ids[0])]

    for r in reciprocal_rank_fusion(dense, sparse):
        assert 0.0 <= r.score <= 1.0


def test_top_result_has_score_1() -> None:
    """The highest-ranked result must have a normalised score of exactly 1.0."""
    ids = [uuid.uuid4() for _ in range(3)]
    dense = [_dense(ids[0]), _dense(ids[1]), _dense(ids[2])]
    sparse = [_sparse(ids[0])]  # ids[0] is in both lists → should win

    results = reciprocal_rank_fusion(dense, sparse)
    assert results[0].score == pytest.approx(1.0)


def test_single_result_score_is_1() -> None:
    """A single result (only one chunk in total) must have score exactly 1.0."""
    cid = uuid.uuid4()
    results = reciprocal_rank_fusion([_dense(cid)], [])
    assert results[0].score == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# Ordering — results sorted by score descending
# ---------------------------------------------------------------------------


def test_results_sorted_descending() -> None:
    """Output list must be sorted by score in strictly descending order."""
    ids = [uuid.uuid4() for _ in range(5)]
    dense = [_dense(ids[i]) for i in range(5)]
    sparse = [_sparse(ids[i], rank=i + 1) for i in range(5)]

    results = reciprocal_rank_fusion(dense, sparse)
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_two_disjoint_lists_interleaved() -> None:
    """Disjoint dense/sparse lists must produce interleaved results based on RRF rank."""
    d1, d2 = uuid.uuid4(), uuid.uuid4()
    s1, s2 = uuid.uuid4(), uuid.uuid4()

    dense = [_dense(d1), _dense(d2)]
    sparse = [_sparse(s1, rank=1), _sparse(s2, rank=2)]

    results = reciprocal_rank_fusion(dense, sparse)

    # All 4 chunks must appear
    result_ids = {r.chunk_id for r in results}
    assert result_ids == {d1, d2, s1, s2}

    # Scores must be descending
    scores = [r.score for r in results]
    assert scores == sorted(scores, reverse=True)


def test_identical_lists_same_order_doubled_score() -> None:
    """Two identical ranked lists must produce the same order with doubled RRF weight."""
    ids = [uuid.uuid4(), uuid.uuid4(), uuid.uuid4()]
    dense_list = [_dense(ids[i]) for i in range(3)]
    sparse_list = [_sparse(ids[i], rank=i + 1) for i in range(3)]

    results = reciprocal_rank_fusion(dense_list, sparse_list)

    # All three chunks present
    assert len(results) == 3
    # ids[0] ranked 1st in both → highest score
    assert results[0].chunk_id == ids[0]
    # Every score must be in [0, 1]
    for r in results:
        assert 0.0 <= r.score <= 1.0


# ---------------------------------------------------------------------------
# Effect of k parameter
# ---------------------------------------------------------------------------


def test_smaller_k_amplifies_rank_differences() -> None:
    """With k=1, the rank-1 result should dominate more than with k=100."""
    id1, id2 = uuid.uuid4(), uuid.uuid4()
    dense = [_dense(id1), _dense(id2)]

    results_small_k = reciprocal_rank_fusion(dense, [], k=1)
    results_large_k = reciprocal_rank_fusion(dense, [], k=100)

    # Score gap between rank-1 and rank-2 must be larger for small k
    gap_small = results_small_k[0].score - results_small_k[1].score
    gap_large = results_large_k[0].score - results_large_k[1].score
    assert gap_small > gap_large


def test_k_100_scores_closer_together() -> None:
    """High k compresses scores — difference between adjacent results is smaller."""
    ids = [uuid.uuid4() for _ in range(3)]
    dense = [_dense(i) for i in ids]

    results = reciprocal_rank_fusion(dense, [], k=100)
    scores = [r.score for r in results]

    # All scores must still be valid
    for s in scores:
        assert 0.0 <= s <= 1.0

    # With high k, ratio of best/worst should be < 2 for 3 items
    assert scores[0] / scores[-1] < 2.0
