"""Generation quality metrics for the FinSage-Lite evaluation harness.

Two evaluation strategies are provided:

* **F1 token-level** (default): fast, reproducible SQuAD-style token-overlap
  scoring.  No external dependencies beyond the standard library.
* **RAGAS** (optional): Answer Correctness, Faithfulness, and Context
  Relevancy via ``ragas.evaluate()``.  Requires
  ``pip install 'finsage-lite[eval]'`` and a running Ollama instance.

The active strategy is selected by the ``RAGAS_ENABLED`` environment variable
(default: ``false``).

Example::

    from evaluation.metrics_generation import f1_token_level, get_strategy

    scores = f1_token_level(
        "Apple reported $394B revenue.",
        "Apple reported $394B revenue.",
    )
    assert scores["f1"] == 1.0

    strategy = get_strategy()
    metrics = strategy.evaluate(
        question="What was Apple's revenue?",
        expected="$394B",
        generated="Apple's revenue was $394B.",
        contexts=["Total net sales were $394 billion."],
    )
"""

from __future__ import annotations

import logging
import os
import re
from collections import Counter
from dataclasses import dataclass
from typing import Protocol

import httpx

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tokenisation helpers
# ---------------------------------------------------------------------------

_STOPWORDS: frozenset[str] = frozenset(
    {
        "the",
        "a",
        "an",
        "is",
        "in",
        "of",
        "and",
        "or",
        "to",
        "for",
        "it",
        "its",
        "was",
        "are",
        "be",
        "by",
        "on",
        "at",
        "as",
        "this",
        "that",
        "with",
        "from",
        "but",
        "not",
        "have",
        "had",
        "has",
        "we",
        "our",
        "their",
    }
)


def _tokenize(text: str) -> list[str]:
    """Lowercase and split text into word-level tokens.

    Splits on whitespace and punctuation; filters stop words and
    single-character tokens.  Financial terms (e.g. ``EBITDA``,
    ``goodwill``) are preserved without stemming.

    Args:
        text: Raw text string to tokenize.

    Returns:
        Filtered list of lowercase tokens.
    """
    lowered = text.lower()
    raw_tokens = re.findall(r"\b[a-z0-9][a-z0-9'.-]*\b", lowered)
    return [t for t in raw_tokens if t not in _STOPWORDS and len(t) > 1]


# ---------------------------------------------------------------------------
# F1 token-level
# ---------------------------------------------------------------------------


def f1_token_level(expected: str, generated: str) -> dict[str, float]:
    """Compute token-level F1 between an expected and a generated answer.

    Uses a multiset (Counter-based) approach that mirrors the official SQuAD
    evaluation script: tokens that appear multiple times in the expected answer
    can each be matched against the same token in the generated answer.

    Args:
        expected: Ground-truth answer string.
        generated: Model-generated answer string.

    Returns:
        Dict with keys ``"precision"``, ``"recall"``, and ``"f1"``, each a
        float in [0, 1].  All three are ``0.0`` when both strings produce an
        empty token list after pre-processing.
    """
    expected_tokens = _tokenize(expected)
    generated_tokens = _tokenize(generated)

    if not expected_tokens and not generated_tokens:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    if not expected_tokens or not generated_tokens:
        return {"precision": 0.0, "recall": 0.0, "f1": 0.0}

    expected_counter = Counter(expected_tokens)
    generated_counter = Counter(generated_tokens)

    # Intersection over multisets: min count for each common token
    common_count = sum((expected_counter & generated_counter).values())

    num_generated = sum(generated_counter.values())
    num_expected = sum(expected_counter.values())

    precision = common_count / num_generated if num_generated else 0.0
    recall = common_count / num_expected if num_expected else 0.0

    if precision + recall == 0.0:
        f1 = 0.0
    else:
        f1 = 2.0 * precision * recall / (precision + recall)

    return {"precision": precision, "recall": recall, "f1": f1}


# ---------------------------------------------------------------------------
# GenerationMetrics result type
# ---------------------------------------------------------------------------


@dataclass
class GenerationMetrics:
    """Per-question generation quality metrics.

    Attributes:
        precision: Token-level precision (F1 approach).
        recall: Token-level recall (F1 approach).
        f1: Token-level F1 score.
        ragas_answer_correctness: RAGAS Answer Correctness score, or ``None``
            if RAGAS was not run for this question.
        ragas_faithfulness: RAGAS Faithfulness score, or ``None`` if RAGAS
            was not run.
        ragas_context_relevancy: RAGAS Context Relevancy score, or ``None``
            if RAGAS was not run.
    """

    precision: float
    recall: float
    f1: float
    ragas_answer_correctness: float | None = None
    ragas_faithfulness: float | None = None
    ragas_context_relevancy: float | None = None


# ---------------------------------------------------------------------------
# Strategy protocol
# ---------------------------------------------------------------------------


class GenerationMetricsStrategy(Protocol):
    """Protocol for generation quality evaluation strategies.

    Both :class:`F1Strategy` and :class:`RAGASStrategy` implement this
    interface, allowing the harness to swap strategies at runtime via
    :func:`get_strategy`.
    """

    def evaluate(
        self,
        question: str,
        expected: str,
        generated: str,
        contexts: list[str],
    ) -> GenerationMetrics:
        """Evaluate the quality of a single generated answer.

        Args:
            question: Original question text.
            expected: Ground-truth answer string.
            generated: Model-generated answer string.
            contexts: Retrieved context passages used for generation.

        Returns:
            :class:`GenerationMetrics` with computed scores.
        """
        ...


# ---------------------------------------------------------------------------
# F1Strategy
# ---------------------------------------------------------------------------


class F1Strategy:
    """Fast, always-available F1 token-level evaluation strategy.

    No external LLM or network access required.
    """

    def evaluate(
        self,
        question: str,
        expected: str,
        generated: str,
        contexts: list[str],
    ) -> GenerationMetrics:
        """Compute token-level F1.

        Args:
            question: Question text (unused; kept for protocol compatibility).
            expected: Ground-truth answer string.
            generated: Model-generated answer string.
            contexts: Context passages (unused; kept for protocol compatibility).

        Returns:
            :class:`GenerationMetrics` with F1 scores; all RAGAS fields are
            ``None``.
        """
        scores = f1_token_level(expected, generated)
        return GenerationMetrics(
            precision=scores["precision"],
            recall=scores["recall"],
            f1=scores["f1"],
        )


# ---------------------------------------------------------------------------
# RAGAS
# ---------------------------------------------------------------------------


class RAGASUnavailableError(Exception):
    """Raised when RAGAS evaluation cannot be performed.

    Possible causes:

    - The ``ragas`` package is not installed (``pip install 'finsage-lite[eval]'``).
    - Ollama is offline or unreachable.
    - RAGAS evaluation raised an unexpected error.
    """


def _ollama_base_url() -> str:
    """Return the Ollama base URL from the environment.

    Returns:
        Value of ``OLLAMA_BASE_URL``, defaulting to ``http://localhost:11434``.
    """
    return os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")


def _ollama_model() -> str:
    """Return the Ollama model name from the environment.

    Returns:
        Value of ``OLLAMA_MODEL``, defaulting to ``mistral``.
    """
    return os.getenv("OLLAMA_MODEL", "mistral")


def ragas_evaluate(
    questions: list[str],
    answers: list[str],
    contexts: list[list[str]],
    ground_truths: list[str],
) -> dict[str, float]:
    """Run RAGAS metrics on a batch of question-answer pairs.

    Uses Mistral (or the model specified via ``OLLAMA_MODEL``) through a
    local Ollama instance (``OLLAMA_BASE_URL``).

    Args:
        questions: Question strings.
        answers: Model-generated answer strings.
        contexts: Per-question lists of retrieved context passages.
        ground_truths: Ground-truth answer strings.

    Returns:
        Dict with keys ``"answer_correctness"``, ``"faithfulness"``, and
        ``"context_relevancy"`` (values averaged over the batch).

    Raises:
        RAGASUnavailableError: If the ``ragas`` package is not installed,
            Ollama is unreachable, or evaluation fails for any other reason.
    """
    try:
        from ragas import evaluate as _ragas_eval  # type: ignore[import-untyped]  # noqa: PLC0415
        from ragas.metrics import (  # type: ignore[import-untyped]  # noqa: PLC0415
            answer_correctness,
            context_relevancy,
            faithfulness,
        )

        from datasets import Dataset  # type: ignore[import-untyped]  # noqa: PLC0415
    except ImportError as exc:
        raise RAGASUnavailableError(
            "ragas/datasets package not installed. Run: pip install 'finsage-lite[eval]'"
        ) from exc

    # Verify Ollama is reachable before attempting evaluation
    base_url = _ollama_base_url()
    try:
        probe = httpx.get(f"{base_url}/api/tags", timeout=3.0)
        probe.raise_for_status()
    except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError) as exc:
        raise RAGASUnavailableError(f"Ollama is unreachable at {base_url}: {exc}") from exc

    # Attempt to configure RAGAS with the local Ollama model
    model_name = _ollama_model()
    try:
        from langchain_community.embeddings import (  # type: ignore[import-untyped]  # noqa: PLC0415
            OllamaEmbeddings,
        )
        from langchain_community.llms import (
            Ollama,  # type: ignore[import-untyped]  # noqa: PLC0415
        )
        from ragas.embeddings import (  # type: ignore[import-untyped]  # noqa: PLC0415
            LangchainEmbeddingsWrapper,
        )
        from ragas.llms import LangchainLLMWrapper  # type: ignore[import-untyped]  # noqa: PLC0415

        llm_wrapper = LangchainLLMWrapper(Ollama(model=model_name, base_url=base_url))
        emb_wrapper = LangchainEmbeddingsWrapper(
            OllamaEmbeddings(model=model_name, base_url=base_url)
        )
        for metric in (answer_correctness, faithfulness, context_relevancy):
            metric.llm = llm_wrapper
            if hasattr(metric, "embeddings"):
                metric.embeddings = emb_wrapper
    except ImportError:
        logger.warning(
            "langchain_community not installed; RAGAS will use its default LLM settings"
        )

    dataset = Dataset.from_dict(
        {
            "question": questions,
            "answer": answers,
            "contexts": contexts,
            "ground_truth": ground_truths,
        }
    )

    try:
        result = _ragas_eval(
            dataset,
            metrics=[answer_correctness, faithfulness, context_relevancy],
        )
    except Exception as exc:
        raise RAGASUnavailableError(f"RAGAS evaluation raised an error: {exc}") from exc

    return {
        "answer_correctness": float(result["answer_correctness"]),
        "faithfulness": float(result["faithfulness"]),
        "context_relevancy": float(result["context_relevancy"]),
    }


# ---------------------------------------------------------------------------
# RAGASStrategy
# ---------------------------------------------------------------------------


class RAGASStrategy:
    """RAGAS evaluation strategy with automatic F1 fallback.

    Always computes F1 token-level metrics.  If RAGAS is available and Ollama
    is reachable, also populates the RAGAS fields in :class:`GenerationMetrics`;
    otherwise they remain ``None`` and a warning is logged.
    """

    def evaluate(
        self,
        question: str,
        expected: str,
        generated: str,
        contexts: list[str],
    ) -> GenerationMetrics:
        """Compute F1 metrics and, when available, RAGAS metrics.

        Args:
            question: Original question text.
            expected: Ground-truth answer string.
            generated: Model-generated answer string.
            contexts: Retrieved context passages used for generation.

        Returns:
            :class:`GenerationMetrics`.  RAGAS fields are populated when
            Ollama is reachable; otherwise they remain ``None``.
        """
        f1_scores = f1_token_level(expected, generated)
        metrics = GenerationMetrics(
            precision=f1_scores["precision"],
            recall=f1_scores["recall"],
            f1=f1_scores["f1"],
        )

        try:
            ragas_scores = ragas_evaluate(
                questions=[question],
                answers=[generated],
                contexts=[contexts],
                ground_truths=[expected],
            )
            metrics.ragas_answer_correctness = ragas_scores["answer_correctness"]
            metrics.ragas_faithfulness = ragas_scores["faithfulness"]
            metrics.ragas_context_relevancy = ragas_scores["context_relevancy"]
        except RAGASUnavailableError as exc:
            logger.warning("RAGAS unavailable, falling back to F1-only: %s", exc)

        return metrics


# ---------------------------------------------------------------------------
# Strategy factory
# ---------------------------------------------------------------------------


def get_strategy() -> GenerationMetricsStrategy:
    """Return the active generation metrics strategy.

    Selection logic based on ``RAGAS_ENABLED`` environment variable:

    * ``RAGAS_ENABLED=true``  → :class:`RAGASStrategy` (F1 fallback active)
    * ``RAGAS_ENABLED=false`` (default) → :class:`F1Strategy`

    Returns:
        An instance implementing :class:`GenerationMetricsStrategy`.
    """
    ragas_enabled = os.getenv("RAGAS_ENABLED", "false").lower() == "true"
    if ragas_enabled:
        logger.info("RAGAS_ENABLED=true — using RAGASStrategy (F1 fallback active)")
        return RAGASStrategy()
    return F1Strategy()
