"""Tests for evaluation/metrics_generation.py.

Covers:
- f1_token_level: perfect match, partial match, no match, edge cases.
- F1Strategy.evaluate: delegates correctly to f1_token_level.
- RAGASStrategy: falls back to F1-only when Ollama is offline
  (RAGAS_ENABLED=true but Ollama unreachable → no exception, RAGAS fields None).
- get_strategy: returns F1Strategy by default, RAGASStrategy when env var set.
"""

from __future__ import annotations

import httpx
import pytest
from evaluation.metrics_generation import (
    F1Strategy,
    GenerationMetrics,
    RAGASStrategy,
    RAGASUnavailableError,
    f1_token_level,
    get_strategy,
)

# ---------------------------------------------------------------------------
# f1_token_level — perfect match
# ---------------------------------------------------------------------------


def test_f1_perfect_match() -> None:
    """F1 = 1.0 when generated equals expected exactly."""
    text = "Apple reported total revenue of 394 billion dollars in fiscal 2022."
    scores = f1_token_level(text, text)
    assert scores["f1"] == pytest.approx(1.0)
    assert scores["precision"] == pytest.approx(1.0)
    assert scores["recall"] == pytest.approx(1.0)


def test_f1_perfect_match_short() -> None:
    """F1 = 1.0 for a short perfect-match pair."""
    scores = f1_token_level("revenue growth", "revenue growth")
    assert scores["f1"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# f1_token_level — partial match
# ---------------------------------------------------------------------------


def test_f1_partial_match_reasonable() -> None:
    """F1 is in (0, 1) for a partially overlapping answer pair."""
    expected = "Apple revenue was 394 billion in fiscal year 2022 driven by iPhone sales."
    generated = "Apple reported revenue of 394 billion in 2022."
    scores = f1_token_level(expected, generated)
    assert 0.0 < scores["f1"] < 1.0
    assert 0.0 < scores["precision"] <= 1.0
    assert 0.0 < scores["recall"] <= 1.0


def test_f1_partial_match_precision_gt_recall() -> None:
    """Precision > Recall when generated is a strict subset of expected tokens."""
    # generated has 2 tokens, both in expected; expected has 4 meaningful tokens
    scores = f1_token_level(
        "revenue growth impairment goodwill",
        "revenue growth",
    )
    # precision = 2/2 = 1.0, recall = 2/4 = 0.5
    assert scores["precision"] == pytest.approx(1.0)
    assert scores["recall"] == pytest.approx(0.5)
    assert scores["f1"] == pytest.approx(2 * 1.0 * 0.5 / (1.0 + 0.5))


# ---------------------------------------------------------------------------
# f1_token_level — no match
# ---------------------------------------------------------------------------


def test_f1_no_match() -> None:
    """F1 = 0.0 when generated and expected share no tokens."""
    scores = f1_token_level(
        "Apple revenue 394 billion",
        "Microsoft cloud services Azure",
    )
    assert scores["f1"] == pytest.approx(0.0)
    assert scores["precision"] == pytest.approx(0.0)
    assert scores["recall"] == pytest.approx(0.0)


# ---------------------------------------------------------------------------
# f1_token_level — edge cases
# ---------------------------------------------------------------------------


def test_f1_both_empty() -> None:
    """f1_token_level returns all zeros when both strings are empty."""
    scores = f1_token_level("", "")
    assert scores == {"precision": 0.0, "recall": 0.0, "f1": 0.0}


def test_f1_empty_expected() -> None:
    """F1 = 0.0 when expected is empty."""
    scores = f1_token_level("", "Apple revenue 394 billion")
    assert scores["f1"] == pytest.approx(0.0)


def test_f1_empty_generated() -> None:
    """F1 = 0.0 when generated is empty."""
    scores = f1_token_level("Apple revenue 394 billion", "")
    assert scores["f1"] == pytest.approx(0.0)


def test_f1_stopwords_only() -> None:
    """Strings containing only stop words produce all-zero scores."""
    scores = f1_token_level("the a an is in", "the a an or to")
    assert scores["f1"] == pytest.approx(0.0)


def test_f1_case_insensitive() -> None:
    """Tokenization is case-insensitive."""
    scores = f1_token_level("APPLE Revenue EBITDA", "apple revenue ebitda")
    assert scores["f1"] == pytest.approx(1.0)


def test_f1_financial_terms_preserved() -> None:
    """Financial terms like EBITDA and goodwill are not truncated by stemming."""
    scores = f1_token_level("ebitda goodwill impairment", "ebitda goodwill impairment")
    assert scores["f1"] == pytest.approx(1.0)


# ---------------------------------------------------------------------------
# F1Strategy.evaluate
# ---------------------------------------------------------------------------


def test_f1_strategy_returns_generation_metrics() -> None:
    """F1Strategy.evaluate returns a GenerationMetrics with correct F1."""
    strategy = F1Strategy()
    metrics = strategy.evaluate(
        question="What was Apple's revenue?",
        expected="Apple revenue 394 billion fiscal 2022",
        generated="Apple revenue 394 billion fiscal 2022",
        contexts=["Total net sales were $394 billion."],
    )
    assert isinstance(metrics, GenerationMetrics)
    assert metrics.f1 == pytest.approx(1.0)
    assert metrics.ragas_answer_correctness is None
    assert metrics.ragas_faithfulness is None
    assert metrics.ragas_context_relevancy is None


def test_f1_strategy_ragas_fields_always_none() -> None:
    """F1Strategy never populates RAGAS fields."""
    strategy = F1Strategy()
    metrics = strategy.evaluate(
        question="q",
        expected="revenue growth impairment",
        generated="revenue growth",
        contexts=[],
    )
    assert metrics.ragas_answer_correctness is None
    assert metrics.ragas_faithfulness is None
    assert metrics.ragas_context_relevancy is None


# ---------------------------------------------------------------------------
# RAGASStrategy — fallback when Ollama offline
# ---------------------------------------------------------------------------


def test_ragas_unavailable_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """RAGASStrategy falls back to F1-only when Ollama is offline.

    With RAGAS_ENABLED=true but Ollama unreachable, evaluate() must:
    - not raise any exception
    - return valid F1 scores
    - leave all RAGAS fields as None
    """
    monkeypatch.setenv("RAGAS_ENABLED", "true")

    # Simulate Ollama being offline
    def _raise_connect_error(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise httpx.ConnectError("Connection refused")

    monkeypatch.setattr(httpx, "get", _raise_connect_error)

    strategy = RAGASStrategy()
    metrics = strategy.evaluate(
        question="What was Apple's revenue?",
        expected="Apple revenue 394 billion",
        generated="Apple revenue 394 billion",
        contexts=["Total net sales were $394 billion."],
    )

    # Must not raise; F1 should be computed
    assert isinstance(metrics, GenerationMetrics)
    assert metrics.f1 == pytest.approx(1.0)

    # RAGAS fields must remain None (graceful fallback)
    assert metrics.ragas_answer_correctness is None
    assert metrics.ragas_faithfulness is None
    assert metrics.ragas_context_relevancy is None


def test_ragas_unavailable_fallback_timeout(monkeypatch: pytest.MonkeyPatch) -> None:
    """RAGASStrategy handles Ollama timeout gracefully."""
    monkeypatch.setenv("RAGAS_ENABLED", "true")

    def _raise_timeout(*args, **kwargs):  # type: ignore[no-untyped-def]
        raise httpx.TimeoutException("Request timed out")

    monkeypatch.setattr(httpx, "get", _raise_timeout)

    strategy = RAGASStrategy()
    metrics = strategy.evaluate(
        question="What are Apple's risk factors?",
        expected="supply chain risk competition",
        generated="supply chain competition",
        contexts=["Risk factors include supply chain issues."],
    )

    assert metrics.f1 > 0.0
    assert metrics.ragas_answer_correctness is None


# ---------------------------------------------------------------------------
# RAGASUnavailableError
# ---------------------------------------------------------------------------


def test_ragas_evaluate_raises_when_unavailable() -> None:
    """ragas_evaluate raises RAGASUnavailableError when ragas is not installed.

    In the dev environment ragas is an optional extra (``pip install
    'finsage-lite[eval]'``), so this test relies on the package being absent.
    If ragas IS present but Ollama is offline the same error is raised; the
    assertion still holds.
    """
    from evaluation.metrics_generation import ragas_evaluate  # noqa: PLC0415

    with pytest.raises(RAGASUnavailableError):
        ragas_evaluate(
            questions=["q"],
            answers=["a"],
            contexts=[["ctx"]],
            ground_truths=["gt"],
        )


# ---------------------------------------------------------------------------
# get_strategy factory
# ---------------------------------------------------------------------------


def test_get_strategy_default_is_f1(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_strategy returns F1Strategy when RAGAS_ENABLED is not set."""
    monkeypatch.delenv("RAGAS_ENABLED", raising=False)
    strategy = get_strategy()
    assert isinstance(strategy, F1Strategy)


def test_get_strategy_false_is_f1(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_strategy returns F1Strategy when RAGAS_ENABLED=false."""
    monkeypatch.setenv("RAGAS_ENABLED", "false")
    strategy = get_strategy()
    assert isinstance(strategy, F1Strategy)


def test_get_strategy_true_is_ragas(monkeypatch: pytest.MonkeyPatch) -> None:
    """get_strategy returns RAGASStrategy when RAGAS_ENABLED=true."""
    monkeypatch.setenv("RAGAS_ENABLED", "true")
    strategy = get_strategy()
    assert isinstance(strategy, RAGASStrategy)
