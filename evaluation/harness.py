"""Evaluation harness for the FinSage-Lite RAG pipeline.

Runs each :class:`~evaluation.schemas.EvalQuestion` from the FinanceBench
corpus against the four pre-defined :data:`EVAL_CONFIGS`, aggregates
retrieval quality metrics, and serializes results to JSON.

When a ``generate_fn`` is provided (e.g. via
:meth:`EvalHarness.make_ollama_generate_fn`), the harness also generates an
answer for each question and computes generation quality metrics
(:func:`~evaluation.metrics_generation.f1_token_level` by default; RAGAS when
``RAGAS_ENABLED=true``).  If Ollama is offline, generation is silently skipped
and all generation fields remain ``None``.

Usage (CLI)::

    python -m evaluation.harness
"""

from __future__ import annotations

import dataclasses
import json
import logging
import time
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import httpx

from evaluation.metrics_generation import GenerationMetrics, get_strategy
from evaluation.metrics_retrieval import (
    find_gold_rank,
    hit_rate_at_k,
    latency_stats,
    mrr,
)
from evaluation.schemas import EvalConfig, EvalQuestion

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Type aliases for the injected callables
# ---------------------------------------------------------------------------

# (query: str, config: EvalConfig) -> (chunk_contents_best_first, latency_ms)
SearchFn = Callable[[str, EvalConfig], tuple[list[str], float]]

# (question: str, contexts: list[str]) -> generated_answer
GenerateFn = Callable[[str, list[str]], str]

# ---------------------------------------------------------------------------
# Financial generation prompt
# ---------------------------------------------------------------------------

_GENERATION_PROMPT_TEMPLATE = """\
You are a financial analyst reviewing SEC 10-K filings.

Context passages:
{context}

Based solely on the context above, answer the following question clearly and \
concisely using specific financial data where available.

Question: {question}

Answer:"""

# ---------------------------------------------------------------------------
# Pre-defined evaluation configurations
# ---------------------------------------------------------------------------

EVAL_CONFIGS: list[EvalConfig] = [
    EvalConfig(name="dense_only", retrieval_mode="dense", hyde_enabled=False),
    EvalConfig(name="bm25_only", retrieval_mode="bm25", hyde_enabled=False),
    EvalConfig(name="hybrid", retrieval_mode="hybrid", rrf_k=60, hyde_enabled=False),
    EvalConfig(name="hybrid_hyde", retrieval_mode="hybrid", rrf_k=60, hyde_enabled=True),
]

# ---------------------------------------------------------------------------
# Result dataclasses
# ---------------------------------------------------------------------------


@dataclass
class QuestionResult:
    """Per-question retrieval outcome for a single evaluation configuration.

    Attributes:
        question_id: 0-based index of the question in the evaluation set.
        question: Original question text.
        config_name: Name of the :class:`~evaluation.schemas.EvalConfig` used.
        retrieved_chunk_ids: Rank-ordered identifiers of the retrieved chunks
            (rank 1 = index 0).
        gold_found: ``True`` if gold evidence was found in the retrieved chunks.
        gold_rank: 1-based rank of the first chunk that contains the gold
            evidence, or ``None`` if not found.
        latency_ms: End-to-end search latency for this question (milliseconds).
        generated_answer: LLM-generated answer, or ``None`` if generation was
            skipped (Ollama offline or no ``generate_fn`` provided).
        f1_score: Token-level F1 score for this question, or ``None`` if
            generation was skipped.
    """

    question_id: int
    question: str
    config_name: str
    retrieved_chunk_ids: list[str]
    gold_found: bool
    gold_rank: int | None
    latency_ms: float
    generated_answer: str | None = None
    f1_score: float | None = None


@dataclass
class EvalResults:
    """Aggregated evaluation results for a single retrieval configuration.

    Attributes:
        config: The :class:`~evaluation.schemas.EvalConfig` used for this run.
        recall_at_1: Recall@1 across all questions.
        recall_at_3: Recall@3 across all questions.
        recall_at_5: Recall@5 across all questions.
        mrr: Mean Reciprocal Rank across all questions.
        hit_rate_at_1: Fraction of questions where gold is in the top-1 result.
        hit_rate_at_3: Fraction of questions where gold is in the top-3 results.
        hit_rate_at_5: Fraction of questions where gold is in the top-5 results.
        latency_p50_ms: Median search latency in milliseconds.
        latency_p95_ms: 95th-percentile search latency in milliseconds.
        latency_p99_ms: 99th-percentile search latency in milliseconds.
        n_questions: Total number of questions evaluated.
        per_question: Per-question result details.
        f1_score: Mean F1 token-level score across all questions for which
            generation was performed, or ``None`` if generation was skipped.
        ragas_answer_correctness: Mean RAGAS Answer Correctness score, or
            ``None`` if RAGAS was not run.
        ragas_faithfulness: Mean RAGAS Faithfulness score, or ``None`` if
            RAGAS was not run.
        ragas_context_relevancy: Mean RAGAS Context Relevancy score, or
            ``None`` if RAGAS was not run.
    """

    config: EvalConfig
    recall_at_1: float
    recall_at_3: float
    recall_at_5: float
    mrr: float
    hit_rate_at_1: float
    hit_rate_at_3: float
    hit_rate_at_5: float
    latency_p50_ms: float
    latency_p95_ms: float
    latency_p99_ms: float
    n_questions: int
    per_question: list[QuestionResult]
    f1_score: float | None = None
    ragas_answer_correctness: float | None = None
    ragas_faithfulness: float | None = None
    ragas_context_relevancy: float | None = None

    def to_dict(self) -> dict:
        """Serialize results to a JSON-compatible dictionary.

        Returns:
            Dict with top-level keys ``config``, ``metrics``,
            ``generation_metrics``, ``latency_stats``, and
            ``per_question_results``.
        """
        return {
            "config": self.config.model_dump(),
            "metrics": {
                "recall_at_1": self.recall_at_1,
                "recall_at_3": self.recall_at_3,
                "recall_at_5": self.recall_at_5,
                "mrr": self.mrr,
                "hit_rate_at_1": self.hit_rate_at_1,
                "hit_rate_at_3": self.hit_rate_at_3,
                "hit_rate_at_5": self.hit_rate_at_5,
                "n_questions": self.n_questions,
            },
            "generation_metrics": {
                "f1_score": self.f1_score,
                "ragas_answer_correctness": self.ragas_answer_correctness,
                "ragas_faithfulness": self.ragas_faithfulness,
                "ragas_context_relevancy": self.ragas_context_relevancy,
            },
            "latency_stats": {
                "p50_ms": self.latency_p50_ms,
                "p95_ms": self.latency_p95_ms,
                "p99_ms": self.latency_p99_ms,
            },
            "per_question_results": [dataclasses.asdict(r) for r in self.per_question],
        }


# ---------------------------------------------------------------------------
# EvalHarness
# ---------------------------------------------------------------------------


class EvalHarness:
    """Orchestrates retrieval (and optionally generation) evaluation.

    The harness delegates all search calls to an injected :data:`SearchFn` and,
    when a :data:`GenerateFn` is supplied, also runs LLM generation and computes
    generation quality metrics.  Both callables are injected for testability.

    Args:
        search_fn: Callable ``(query, config) → (chunk_contents, latency_ms)``.
            ``chunk_contents`` must be ordered best-first (rank 1 = index 0).
        generate_fn: Optional callable ``(question, contexts) → answer``.
            When ``None``, generation and all generation metrics are skipped.
    """

    def __init__(
        self,
        search_fn: SearchFn,
        generate_fn: GenerateFn | None = None,
    ) -> None:
        self._search_fn = search_fn
        self._generate_fn = generate_fn

    @staticmethod
    def make_ollama_generate_fn(
        base_url: str = "http://localhost:11434",
        model: str = "mistral",
        timeout: float = 30.0,
    ) -> GenerateFn | None:
        """Create a generation callable backed by a local Ollama instance.

        Probes Ollama availability before returning.  Returns ``None`` if
        Ollama is unreachable so callers can enable graceful degradation.

        Args:
            base_url: Ollama base URL (no trailing slash).
            model: Model name served by Ollama (default: ``mistral``).
            timeout: Per-request timeout in seconds.

        Returns:
            Synchronous :data:`GenerateFn`, or ``None`` if Ollama is offline.
        """
        try:
            probe = httpx.get(f"{base_url}/api/tags", timeout=3.0)
            probe.raise_for_status()
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPStatusError):
            logger.warning("Ollama not reachable at %s — generation disabled", base_url)
            return None

        def _fn(question: str, contexts: list[str]) -> str:
            context_text = "\n\n".join(contexts)
            prompt = _GENERATION_PROMPT_TEMPLATE.format(context=context_text, question=question)
            resp = httpx.post(
                f"{base_url}/api/generate",
                json={"model": model, "prompt": prompt, "stream": False},
                timeout=timeout,
            )
            resp.raise_for_status()
            return str(resp.json().get("response", ""))

        return _fn

    @staticmethod
    def make_api_search_fn(
        api_base_url: str = "http://localhost:8000",
        timeout: float = 30.0,
    ) -> SearchFn:
        """Create a search function that calls the live FinSage-Lite HTTP API.

        Uses httpx's synchronous client — the eval harness is an offline batch
        script and does not require async I/O.

        Args:
            api_base_url: Base URL of the running API (no trailing slash).
            timeout: Per-request timeout in seconds.

        Returns:
            Synchronous callable suitable for use as ``EvalHarness``'s
            ``search_fn`` argument.
        """

        def fn(query: str, config: EvalConfig) -> tuple[list[str], float]:
            payload = {
                "query": query,
                "top_k": config.top_k,
                "search_mode": config.retrieval_mode,
                "use_hyde": config.hyde_enabled,
            }
            t0 = time.perf_counter()
            resp = httpx.post(
                f"{api_base_url}/api/v1/search",
                json=payload,
                timeout=timeout,
            )
            resp.raise_for_status()
            latency_ms = (time.perf_counter() - t0) * 1000
            data = resp.json()
            return [r["content"] for r in data.get("results", [])], latency_ms

        return fn

    def run(
        self,
        config: EvalConfig,
        questions: list[EvalQuestion],
    ) -> EvalResults:
        """Evaluate a single configuration against a list of questions.

        For each question the harness:

        1. Calls ``search_fn`` to obtain ranked chunk contents and latency.
        2. Locates the gold evidence (``evidence_text`` or ``expected_answer``)
           within the retrieved chunks using
           :func:`~evaluation.metrics_retrieval.find_gold_rank`.
        3. Records the 1-based gold rank (``None`` if not found) and latency.
        4. If a ``generate_fn`` was provided, generates an answer from the
           retrieved context and computes generation metrics (F1, and RAGAS
           when ``RAGAS_ENABLED=true``).

        Questions for which gold evidence is not found in any chunk are logged
        at ``DEBUG`` level.

        Args:
            config: Retrieval configuration to evaluate.
            questions: Questions to run.

        Returns:
            :class:`EvalResults` with aggregated retrieval and generation
            metrics, plus per-question details.
        """
        per_question: list[QuestionResult] = []
        latencies: list[float] = []
        gen_metrics_list: list[GenerationMetrics] = []

        generation_strategy = get_strategy() if self._generate_fn is not None else None

        for q_id, question in enumerate(questions):
            gold = question.evidence_text or question.expected_answer
            contents, latency_ms = self._search_fn(question.question, config)
            latencies.append(latency_ms)

            rank = find_gold_rank(contents, gold)

            # ---- optional generation -----------------------------------------
            generated_answer: str | None = None
            q_f1: float | None = None

            if self._generate_fn is not None and generation_strategy is not None:
                try:
                    generated_answer = self._generate_fn(question.question, contents)
                    gen_m = generation_strategy.evaluate(
                        question=question.question,
                        expected=question.expected_answer,
                        generated=generated_answer,
                        contexts=contents,
                    )
                    q_f1 = gen_m.f1
                    gen_metrics_list.append(gen_m)
                except Exception as exc:  # noqa: BLE001
                    logger.warning(
                        "[%s] Generation failed for q%d: %s",
                        config.name,
                        q_id,
                        exc,
                    )

            per_question.append(
                QuestionResult(
                    question_id=q_id,
                    question=question.question,
                    config_name=config.name,
                    retrieved_chunk_ids=[str(i + 1) for i in range(len(contents))],
                    gold_found=rank is not None,
                    gold_rank=rank,
                    latency_ms=latency_ms,
                    generated_answer=generated_answer,
                    f1_score=q_f1,
                )
            )

            if rank is None:
                logger.debug(
                    "[%s] Gold not found — q%d: %r",
                    config.name,
                    q_id,
                    question.question[:80],
                )

        # ---- aggregate retrieval metrics -------------------------------------
        ranks = [r.gold_rank for r in per_question]
        hits_1 = [r.gold_rank is not None and r.gold_rank <= 1 for r in per_question]
        hits_3 = [r.gold_rank is not None and r.gold_rank <= 3 for r in per_question]
        hits_5 = [r.gold_rank is not None and r.gold_rank <= 5 for r in per_question]

        stats = latency_stats(latencies)
        r1 = hit_rate_at_k(hits_1)
        r3 = hit_rate_at_k(hits_3)
        r5 = hit_rate_at_k(hits_5)

        not_found = sum(1 for r in per_question if not r.gold_found)
        if not_found:
            logger.warning(
                "[%s] Gold evidence not found for %d / %d questions",
                config.name,
                not_found,
                len(per_question),
            )

        # ---- aggregate generation metrics ------------------------------------
        avg_f1: float | None = None
        avg_ragas_ac: float | None = None
        avg_ragas_faith: float | None = None
        avg_ragas_cr: float | None = None

        if gen_metrics_list:
            avg_f1 = sum(m.f1 for m in gen_metrics_list) / len(gen_metrics_list)

            ragas_ac = [
                m.ragas_answer_correctness
                for m in gen_metrics_list
                if m.ragas_answer_correctness is not None
            ]
            ragas_faith = [
                m.ragas_faithfulness for m in gen_metrics_list if m.ragas_faithfulness is not None
            ]
            ragas_cr = [
                m.ragas_context_relevancy
                for m in gen_metrics_list
                if m.ragas_context_relevancy is not None
            ]

            avg_ragas_ac = sum(ragas_ac) / len(ragas_ac) if ragas_ac else None
            avg_ragas_faith = sum(ragas_faith) / len(ragas_faith) if ragas_faith else None
            avg_ragas_cr = sum(ragas_cr) / len(ragas_cr) if ragas_cr else None

            logger.info(
                "[%s] generation: avg_f1=%.3f  ragas_ac=%s",
                config.name,
                avg_f1,
                f"{avg_ragas_ac:.3f}" if avg_ragas_ac is not None else "n/a",
            )

        return EvalResults(
            config=config,
            recall_at_1=r1,
            recall_at_3=r3,
            recall_at_5=r5,
            mrr=mrr(ranks),
            hit_rate_at_1=r1,
            hit_rate_at_3=r3,
            hit_rate_at_5=r5,
            latency_p50_ms=stats["p50"],
            latency_p95_ms=stats["p95"],
            latency_p99_ms=stats["p99"],
            n_questions=len(questions),
            per_question=per_question,
            f1_score=avg_f1,
            ragas_answer_correctness=avg_ragas_ac,
            ragas_faithfulness=avg_ragas_faith,
            ragas_context_relevancy=avg_ragas_cr,
        )

    def run_all(self, questions: list[EvalQuestion]) -> list[EvalResults]:
        """Run all pre-defined :data:`EVAL_CONFIGS` sequentially.

        Args:
            questions: Evaluation questions to run for each configuration.

        Returns:
            List of :class:`EvalResults`, one per entry in :data:`EVAL_CONFIGS`
            in the same order.
        """
        all_results: list[EvalResults] = []
        for config in EVAL_CONFIGS:
            logger.info("Running config: %s (%d questions) …", config.name, len(questions))
            result = self.run(config, questions)
            logger.info(
                "[%s] recall@5=%.3f  mrr=%.3f  p50=%.0f ms",
                config.name,
                result.recall_at_5,
                result.mrr,
                result.latency_p50_ms,
            )
            all_results.append(result)
        return all_results

    def save_results(self, results: EvalResults, output_dir: Path) -> Path:
        """Serialize :class:`EvalResults` to a timestamped JSON file.

        The filename follows the pattern
        ``eval_{config_name}_{YYYYMMDD_HHMMSS}.json``.

        Args:
            results: Evaluation results to persist.
            output_dir: Target directory (created automatically if absent).

        Returns:
            Absolute path to the created JSON file.
        """
        output_dir.mkdir(parents=True, exist_ok=True)
        ts = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")
        filename = f"eval_{results.config.name}_{ts}.json"
        output_path = output_dir / filename
        output_path.write_text(json.dumps(results.to_dict(), indent=2), encoding="utf-8")
        logger.info("Results saved → %s", output_path)
        return output_path


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _main() -> None:
    """Run all evaluation configurations against the FinanceBench corpus."""
    import sys  # noqa: PLC0415

    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )

    try:
        from evaluation.datasets.financebench import FinanceBenchLoader  # noqa: PLC0415
    except ImportError:
        logger.error("Could not import FinanceBenchLoader. Run: pip install datasets")
        sys.exit(1)

    loader = FinanceBenchLoader()
    logger.info("Loading FinanceBench dataset …")
    questions = loader.load()

    if not questions:
        logger.error("No questions loaded — check dataset availability.")
        sys.exit(1)

    logger.info("Loaded %d questions", len(questions))

    search_fn = EvalHarness.make_api_search_fn()
    generate_fn = EvalHarness.make_ollama_generate_fn()
    harness = EvalHarness(search_fn=search_fn, generate_fn=generate_fn)
    output_dir = Path("evaluation/results")

    all_results = harness.run_all(questions)
    print("\n=== Evaluation Summary ===")
    for result in all_results:
        path = harness.save_results(result, output_dir)
        print(
            f"  {result.config.name:<20}  "
            f"recall@5={result.recall_at_5:.3f}  "
            f"mrr={result.mrr:.3f}  "
            f"→ {path.name}"
        )


if __name__ == "__main__":
    _main()
