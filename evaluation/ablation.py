"""Ablation studies for the FinSage-Lite RAG pipeline.

Runs two types of ablation:

* **RRF k ablation** — sweeps the RRF constant *k* across ``[10, 30, 60, 100]``
  using the hybrid retrieval mode without HyDE.
* **HyDE ablation** — compares hybrid retrieval with and without HyDE,
  optionally grouped by question category.

Usage (CLI)::

    python -m evaluation.ablation
"""

from __future__ import annotations

import logging

from evaluation.harness import EvalHarness, EvalResults
from evaluation.schemas import EvalConfig, EvalQuestion

logger = logging.getLogger(__name__)

_DEFAULT_K_VALUES: list[int] = [10, 30, 60, 100]


class AblationRunner:
    """Executes ablation studies on the evaluation corpus.

    Args:
        harness: Configured :class:`~evaluation.harness.EvalHarness` instance.
        questions: Evaluation questions to run ablations against.
    """

    def __init__(self, harness: EvalHarness, questions: list[EvalQuestion]) -> None:
        self._harness = harness
        self._questions = questions

    def run_rrf_ablation(
        self,
        k_values: list[int] | None = None,
    ) -> list[EvalResults]:
        """Test hybrid retrieval (no HyDE) across a range of RRF k constants.

        Evaluates the ``hybrid`` configuration for each *k* value, varying only
        the RRF constant while keeping all other parameters fixed at their
        defaults (``top_k=5``, ``hyde_enabled=False``).

        Args:
            k_values: RRF constants to test. Defaults to ``[10, 30, 60, 100]``.

        Returns:
            One :class:`~evaluation.harness.EvalResults` per k value, in the
            same order as *k_values*.
        """
        resolved = k_values if k_values is not None else _DEFAULT_K_VALUES
        results: list[EvalResults] = []
        for k in resolved:
            config = EvalConfig(
                name=f"hybrid_rrf_k{k}",
                retrieval_mode="hybrid",
                rrf_k=k,
                hyde_enabled=False,
            )
            logger.info("RRF ablation — k=%d (%d questions) …", k, len(self._questions))
            result = self._harness.run(config, self._questions)
            logger.info(
                "  k=%-4d  recall@5=%.3f  mrr=%.3f  p50=%.0f ms",
                k,
                result.recall_at_5,
                result.mrr,
                result.latency_p50_ms,
            )
            results.append(result)
        return results

    def run_hyde_ablation(self) -> dict[str, list[EvalResults]]:
        """Compare hybrid retrieval with and without HyDE, grouped by category.

        If the question set contains at least one non-null ``category`` field,
        results are grouped by category value.  Otherwise a single ``"global"``
        group covering all questions is used.

        Returns:
            Mapping of group label → ``[without_hyde_result, with_hyde_result]``
            where each value is a two-element list of
            :class:`~evaluation.harness.EvalResults`.
        """
        categories = sorted({q.category for q in self._questions if q.category is not None})

        if not categories:
            logger.info("HyDE ablation — no categories found, running global comparison …")
            no_hyde = self._harness.run(
                EvalConfig(
                    name="hybrid",
                    retrieval_mode="hybrid",
                    rrf_k=60,
                    hyde_enabled=False,
                ),
                self._questions,
            )
            with_hyde = self._harness.run(
                EvalConfig(
                    name="hybrid_hyde",
                    retrieval_mode="hybrid",
                    rrf_k=60,
                    hyde_enabled=True,
                ),
                self._questions,
            )
            return {"global": [no_hyde, with_hyde]}

        output: dict[str, list[EvalResults]] = {}
        for category in categories:
            subset = [q for q in self._questions if q.category == category]
            logger.info("HyDE ablation — category=%r  n=%d", category, len(subset))
            no_hyde = self._harness.run(
                EvalConfig(
                    name=f"hybrid_{category}",
                    retrieval_mode="hybrid",
                    rrf_k=60,
                    hyde_enabled=False,
                ),
                subset,
            )
            with_hyde = self._harness.run(
                EvalConfig(
                    name=f"hybrid_hyde_{category}",
                    retrieval_mode="hybrid",
                    rrf_k=60,
                    hyde_enabled=True,
                ),
                subset,
            )
            output[category] = [no_hyde, with_hyde]
        return output


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _main() -> None:
    """Run all ablation studies against the FinanceBench corpus and print a summary."""
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
    harness = EvalHarness(search_fn=search_fn)
    runner = AblationRunner(harness=harness, questions=questions)

    print("\n=== RRF k Ablation ===")
    rrf_results = runner.run_rrf_ablation()
    for r in rrf_results:
        print(f"  k={r.config.rrf_k:<4}  recall@5={r.recall_at_5:.3f}  mrr={r.mrr:.3f}")

    print("\n=== HyDE Ablation ===")
    hyde_results = runner.run_hyde_ablation()
    for group, pair in hyde_results.items():
        no_hyde, with_hyde = pair
        delta = with_hyde.recall_at_5 - no_hyde.recall_at_5
        print(
            f"  {group:<15}  no_hyde={no_hyde.recall_at_5:.3f}"
            f"  with_hyde={with_hyde.recall_at_5:.3f}  Δ={delta:+.3f}"
        )


if __name__ == "__main__":
    _main()
