"""Tests for EvalHarness and retrieval quality metrics."""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from evaluation.harness import EVAL_CONFIGS, EvalConfig, EvalHarness, QuestionResult
from evaluation.metrics_retrieval import (
    find_gold_rank,
    hit_rate_at_k,
    latency_stats,
    mrr,
    recall_at_k,
)
from evaluation.schemas import EvalQuestion

# ---------------------------------------------------------------------------
# Shared test data
# ---------------------------------------------------------------------------

GOLD_TEXT = "Total net sales were $394.3 billion for fiscal year 2022."

FIVE_QUESTIONS: list[EvalQuestion] = [
    EvalQuestion(
        question=f"Question {i}?",
        expected_answer="$394 billion",
        evidence_text=GOLD_TEXT,
        company="Apple",
        fiscal_year=2022,
    )
    for i in range(5)
]


def _make_search_fn(per_call_contents: list[list[str]]):  # type: ignore[return]
    """Return a mock search function that yields pre-defined results per call.

    Args:
        per_call_contents: List of chunk-content lists, one per expected call.

    Returns:
        Synchronous callable compatible with :data:`~evaluation.harness.SearchFn`.
    """
    calls = iter(per_call_contents)

    def fn(query: str, config: EvalConfig) -> tuple[list[str], float]:
        try:
            return next(calls), 10.0
        except StopIteration:
            return [], 10.0

    return fn


# ---------------------------------------------------------------------------
# find_gold_rank
# ---------------------------------------------------------------------------


def test_find_gold_rank_exact_match() -> None:
    """find_gold_rank returns 1 when gold text is the first chunk."""
    assert find_gold_rank([GOLD_TEXT, "other chunk"], GOLD_TEXT) == 1


def test_find_gold_rank_second_position() -> None:
    """find_gold_rank returns 2 when gold text is the second chunk."""
    assert find_gold_rank(["irrelevant", GOLD_TEXT], GOLD_TEXT) == 2


def test_find_gold_rank_not_found() -> None:
    """find_gold_rank returns None when gold text is absent from all chunks."""
    assert find_gold_rank(["chunk A", "chunk B"], GOLD_TEXT) is None


def test_find_gold_rank_empty_gold() -> None:
    """find_gold_rank returns None for an empty gold string."""
    assert find_gold_rank(["some content"], "") is None


# ---------------------------------------------------------------------------
# recall_at_k
# ---------------------------------------------------------------------------


def test_recall_at_k_perfect() -> None:
    """recall_at_k = 1.0 when gold evidence is at rank 1."""
    contents = [GOLD_TEXT, "some irrelevant text", "another irrelevant chunk"]
    assert recall_at_k(contents, GOLD_TEXT, k=5) == 1.0


def test_recall_at_k_miss() -> None:
    """recall_at_k = 0.0 when gold evidence is absent from all retrieved chunks."""
    contents = ["irrelevant content A", "irrelevant content B"]
    assert recall_at_k(contents, GOLD_TEXT, k=5) == 0.0


def test_recall_at_k_beyond_cutoff() -> None:
    """recall_at_k = 0.0 when gold is present but beyond the top-k cutoff."""
    contents = ["irrelevant", "irrelevant", GOLD_TEXT]
    assert recall_at_k(contents, GOLD_TEXT, k=2) == 0.0


def test_recall_at_k_at_boundary() -> None:
    """recall_at_k = 1.0 when gold is exactly at position k."""
    contents = ["irrelevant", "irrelevant", GOLD_TEXT]
    assert recall_at_k(contents, GOLD_TEXT, k=3) == 1.0


# ---------------------------------------------------------------------------
# mrr
# ---------------------------------------------------------------------------


def test_mrr_calculation() -> None:
    """mrr() correctly applies the 1/rank formula."""
    ranks: list[int | None] = [1, 2, None]
    expected = (1.0 / 1 + 1.0 / 2 + 0.0) / 3
    assert abs(mrr(ranks) - expected) < 1e-9


def test_mrr_all_found_rank_one() -> None:
    """mrr() = 1.0 when every question has gold at rank 1."""
    assert mrr([1, 1, 1]) == 1.0


def test_mrr_none_found() -> None:
    """mrr() = 0.0 when gold is never found."""
    ranks: list[int | None] = [None, None]
    assert mrr(ranks) == 0.0


def test_mrr_empty() -> None:
    """mrr() = 0.0 for an empty list."""
    assert mrr([]) == 0.0


# ---------------------------------------------------------------------------
# hit_rate_at_k
# ---------------------------------------------------------------------------


def test_hit_rate_all_hits() -> None:
    """hit_rate_at_k = 1.0 when every question is a hit."""
    assert hit_rate_at_k([True, True, True]) == 1.0


def test_hit_rate_no_hits() -> None:
    """hit_rate_at_k = 0.0 when no question is a hit."""
    assert hit_rate_at_k([False, False]) == 0.0


def test_hit_rate_partial() -> None:
    """hit_rate_at_k = 0.5 for 1 out of 2 hits."""
    assert hit_rate_at_k([True, False]) == 0.5


def test_hit_rate_empty() -> None:
    """hit_rate_at_k = 0.0 for an empty list."""
    assert hit_rate_at_k([]) == 0.0


# ---------------------------------------------------------------------------
# latency_stats
# ---------------------------------------------------------------------------


def test_latency_stats_percentiles() -> None:
    """latency_stats() returns p50, p95, p99 keys with monotonically ordered values."""
    latencies = [float(i) for i in range(1, 101)]  # 1.0 … 100.0 ms
    stats = latency_stats(latencies)
    assert "p50" in stats
    assert "p95" in stats
    assert "p99" in stats
    assert stats["p50"] < stats["p95"] <= stats["p99"]


def test_latency_stats_single_value() -> None:
    """latency_stats() works with a single measurement (all percentiles equal)."""
    stats = latency_stats([42.0])
    assert stats["p50"] == pytest.approx(42.0)
    assert stats["p95"] == pytest.approx(42.0)
    assert stats["p99"] == pytest.approx(42.0)


def test_latency_stats_empty() -> None:
    """latency_stats() returns all-zero dict for an empty list."""
    assert latency_stats([]) == {"p50": 0.0, "p95": 0.0, "p99": 0.0}


# ---------------------------------------------------------------------------
# EvalHarness.run()
# ---------------------------------------------------------------------------


def test_harness_run_perfect_retrieval() -> None:
    """EvalHarness.run() returns recall@5 = mrr = 1.0 when gold is always at rank 1."""
    search_results = [[GOLD_TEXT, "other chunk"] for _ in FIVE_QUESTIONS]
    harness = EvalHarness(search_fn=_make_search_fn(search_results))
    config = EvalConfig(name="test", retrieval_mode="hybrid")
    results = harness.run(config=config, questions=FIVE_QUESTIONS)

    assert results.recall_at_5 == 1.0
    assert results.mrr == 1.0
    assert results.n_questions == 5


def test_harness_run_no_retrieval() -> None:
    """EvalHarness.run() returns recall@5 = mrr = 0.0 when gold is never found."""
    search_results = [["irrelevant chunk"] for _ in FIVE_QUESTIONS]
    harness = EvalHarness(search_fn=_make_search_fn(search_results))
    config = EvalConfig(name="test", retrieval_mode="dense")
    results = harness.run(config=config, questions=FIVE_QUESTIONS)

    assert results.recall_at_5 == 0.0
    assert results.mrr == 0.0


def test_harness_per_question_count() -> None:
    """EvalHarness.run() produces one QuestionResult per question."""
    search_results = [[GOLD_TEXT] for _ in FIVE_QUESTIONS]
    harness = EvalHarness(search_fn=_make_search_fn(search_results))
    config = EvalConfig(name="test", retrieval_mode="hybrid")
    results = harness.run(config=config, questions=FIVE_QUESTIONS)

    assert len(results.per_question) == 5
    for i, qr in enumerate(results.per_question):
        assert isinstance(qr, QuestionResult)
        assert qr.question_id == i
        assert qr.config_name == "test"


def test_harness_gold_rank_stored() -> None:
    """QuestionResult.gold_rank reflects the actual retrieval rank."""
    # Gold is at index 1 (rank 2) for every question
    search_results = [["irrelevant", GOLD_TEXT] for _ in FIVE_QUESTIONS]
    harness = EvalHarness(search_fn=_make_search_fn(search_results))
    config = EvalConfig(name="test", retrieval_mode="hybrid")
    results = harness.run(config=config, questions=FIVE_QUESTIONS)

    for qr in results.per_question:
        assert qr.gold_found is True
        assert qr.gold_rank == 2

    # recall@1 = 0 (gold not at rank 1), recall@3 = 1 (gold at rank 2)
    assert results.recall_at_1 == 0.0
    assert results.recall_at_3 == 1.0


# ---------------------------------------------------------------------------
# EvalHarness.save_results()
# ---------------------------------------------------------------------------


def test_results_serialized(tmp_path: Path) -> None:
    """save_results() creates a valid JSON file with the expected top-level keys."""
    search_results = [[GOLD_TEXT] for _ in FIVE_QUESTIONS]
    harness = EvalHarness(search_fn=_make_search_fn(search_results))
    config = EvalConfig(name="json_test", retrieval_mode="hybrid")
    results = harness.run(config=config, questions=FIVE_QUESTIONS)

    path = harness.save_results(results, output_dir=tmp_path)

    assert path.exists()
    data = json.loads(path.read_text())
    assert "config" in data
    assert "metrics" in data
    assert "latency_stats" in data
    assert "per_question_results" in data
    assert data["metrics"]["n_questions"] == 5
    assert data["config"]["name"] == "json_test"
    assert len(data["per_question_results"]) == 5


def test_results_filename_contains_config_name(tmp_path: Path) -> None:
    """save_results() embeds the config name in the output filename."""
    harness = EvalHarness(search_fn=_make_search_fn([[GOLD_TEXT]]))
    config = EvalConfig(name="my_config", retrieval_mode="dense")
    results = harness.run(config=config, questions=FIVE_QUESTIONS[:1])
    path = harness.save_results(results, output_dir=tmp_path)
    assert "my_config" in path.name


# ---------------------------------------------------------------------------
# EVAL_CONFIGS
# ---------------------------------------------------------------------------


def test_eval_configs_defined() -> None:
    """EVAL_CONFIGS contains exactly the 4 required named configurations."""
    names = {c.name for c in EVAL_CONFIGS}
    assert names == {"dense_only", "bm25_only", "hybrid", "hybrid_hyde"}


def test_eval_configs_hybrid_hyde_enabled() -> None:
    """The hybrid_hyde config has hyde_enabled=True and retrieval_mode='hybrid'."""
    cfg = next(c for c in EVAL_CONFIGS if c.name == "hybrid_hyde")
    assert cfg.hyde_enabled is True
    assert cfg.retrieval_mode == "hybrid"
