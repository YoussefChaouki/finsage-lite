"""Markdown evaluation report generator for FinSage-Lite.

Reads all ``eval_*.json`` files produced by
:class:`~evaluation.harness.EvalHarness` from a results directory and
generates a single, self-contained Markdown report suitable for publishing
in a README or blog post.

The report contains six sections:

1. Configuration Comparison
2. RRF k Ablation (Hybrid, HyDE=False)
3. HyDE Impact (global or per-category)
4. Generation Quality
5. Key Findings (auto-generated)
6. Recommendation (best config + rationale)

Usage (CLI)::

    python -m evaluation.report_generator
"""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime
from pathlib import Path

from evaluation.harness import EvalResults, QuestionResult
from evaluation.schemas import EvalConfig

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Deserialization helpers
# ---------------------------------------------------------------------------

_STANDARD_CONFIG_NAMES = {"dense_only", "bm25_only", "hybrid", "hybrid_hyde"}
_RRF_PREFIX = "hybrid_rrf_k"
_HYDE_CATEGORY_PREFIXES = ("hybrid_hyde_", "hybrid_")


def _results_from_dict(data: dict) -> EvalResults:
    """Reconstruct an :class:`~evaluation.harness.EvalResults` from its dict form.

    Args:
        data: Dictionary as produced by :meth:`~evaluation.harness.EvalResults.to_dict`.

    Returns:
        Fully populated :class:`~evaluation.harness.EvalResults` instance.
    """
    config = EvalConfig(**data["config"])
    per_q = [QuestionResult(**r) for r in data.get("per_question_results", [])]
    metrics = data["metrics"]
    gen = data.get("generation_metrics", {})
    lat = data["latency_stats"]
    return EvalResults(
        config=config,
        recall_at_1=float(metrics["recall_at_1"]),
        recall_at_3=float(metrics["recall_at_3"]),
        recall_at_5=float(metrics["recall_at_5"]),
        mrr=float(metrics["mrr"]),
        hit_rate_at_1=float(metrics["hit_rate_at_1"]),
        hit_rate_at_3=float(metrics["hit_rate_at_3"]),
        hit_rate_at_5=float(metrics["hit_rate_at_5"]),
        latency_p50_ms=float(lat["p50_ms"]),
        latency_p95_ms=float(lat["p95_ms"]),
        latency_p99_ms=float(lat["p99_ms"]),
        n_questions=int(metrics["n_questions"]),
        per_question=per_q,
        f1_score=gen.get("f1_score"),
        ragas_answer_correctness=gen.get("ragas_answer_correctness"),
        ragas_faithfulness=gen.get("ragas_faithfulness"),
        ragas_context_relevancy=gen.get("ragas_context_relevancy"),
    )


# ---------------------------------------------------------------------------
# ReportGenerator
# ---------------------------------------------------------------------------


class ReportGenerator:
    """Generates a Markdown evaluation report from JSON result files.

    The generator reads every ``eval_*.json`` file in the supplied
    *results_dir*, classifies each result as a standard configuration,
    an RRF-k ablation run, or a HyDE ablation run, and assembles a
    structured report with comparison tables and auto-generated findings.
    """

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def generate(
        self,
        results_dir: Path,
        output_dir: Path | None = None,
    ) -> Path:
        """Read all JSON results and write a Markdown report.

        Scans *results_dir* for files matching ``eval_*.json``, loads them,
        and writes a timestamped report to *output_dir* (defaults to
        ``results_dir/../reports``).

        Args:
            results_dir: Directory containing ``eval_*.json`` files produced
                by :class:`~evaluation.harness.EvalHarness`.
            output_dir: Directory to write the report into.  Created
                automatically if absent.  Defaults to
                ``results_dir.parent / "reports"``.

        Returns:
            Absolute path to the generated Markdown file.

        Raises:
            FileNotFoundError: If *results_dir* does not exist.
            ValueError: If no valid JSON result files are found.
        """
        if not results_dir.exists():
            raise FileNotFoundError(f"Results directory not found: {results_dir}")

        resolved_output_dir = (
            output_dir if output_dir is not None else results_dir.parent / "reports"
        )
        resolved_output_dir.mkdir(parents=True, exist_ok=True)

        all_results = self._load_results(results_dir)
        if not all_results:
            raise ValueError(f"No valid eval_*.json files found in {results_dir}")

        # Partition results by type
        standard = [r for r in all_results if r.config.name in _STANDARD_CONFIG_NAMES]
        rrf_ablation = sorted(
            [r for r in all_results if r.config.name.startswith(_RRF_PREFIX)],
            key=lambda r: r.config.rrf_k,
        )
        # HyDE ablation: pairs of "hybrid_<cat>" and "hybrid_hyde_<cat>"
        hyde_ablation = [
            r
            for r in all_results
            if r.config.name not in _STANDARD_CONFIG_NAMES
            and not r.config.name.startswith(_RRF_PREFIX)
        ]

        # Metadata
        n_questions = max((r.n_questions for r in all_results), default=0)
        timestamp = datetime.now(tz=UTC).strftime("%Y-%m-%d %H:%M UTC")
        ts_filename = datetime.now(tz=UTC).strftime("%Y%m%d_%H%M%S")

        sections: list[str] = []

        # --- Header ---------------------------------------------------------
        sections.append(
            f"# FinSage-Lite — Evaluation Report\n\n"
            f"**Date** : {timestamp}  \n"
            f"**Corpus** : FinanceBench subset | {n_questions} questions  \n"
            f"**Target** : Recall@5 ≥ 85%\n"
        )

        # --- Section 1 : Configuration Comparison ---------------------------
        if standard:
            sections.append("## 1. Configuration Comparison\n")
            sections.append(self._format_comparison_table(standard))
        else:
            sections.append(
                "## 1. Configuration Comparison\n\n_No standard configuration results found._\n"
            )

        # --- Section 2 : RRF k Ablation -------------------------------------
        sections.append("## 2. RRF k Ablation (Hybrid, HyDE=False)\n")
        if rrf_ablation:
            sections.append(self._format_ablation_table(rrf_ablation))
        else:
            sections.append("_No RRF ablation results found. Run `make ablation` first._\n")

        # --- Section 3 : HyDE Impact ----------------------------------------
        sections.append("## 3. HyDE Impact\n")
        if hyde_ablation:
            sections.append(self._format_hyde_table(hyde_ablation))
        elif standard:
            # Fall back to comparing hybrid vs hybrid_hyde from standard configs
            hybrid_pairs = self._extract_hyde_pairs_from_standard(standard)
            if hybrid_pairs:
                sections.append(self._format_hyde_table(hybrid_pairs))
            else:
                sections.append("_HyDE comparison data not available._\n")
        else:
            sections.append("_HyDE comparison data not available._\n")

        # --- Section 4 : Generation Quality ---------------------------------
        sections.append("## 4. Generation Quality\n")
        gen_results = [r for r in all_results if r.f1_score is not None]
        if gen_results:
            sections.append(self._format_generation_table(gen_results))
        else:
            sections.append(
                "_Generation metrics not available. Re-run with a `generate_fn` "
                "or set `RAGAS_ENABLED=true`._\n"
            )

        # --- Section 5 : Key Findings ---------------------------------------
        sections.append("## 5. Key Findings\n")
        findings = self._generate_findings(all_results)
        if findings:
            sections.append("\n".join(f"- {f}" for f in findings) + "\n")
        else:
            sections.append("_Insufficient data to generate automatic findings._\n")

        # --- Section 6 : Recommendation -------------------------------------
        sections.append("## 6. Recommendation\n")
        if standard:
            best = self._best_config(standard)
            rationale = self._generate_rationale(best, standard)
            sections.append(f"**Best config** : `{best}`  \n**Rationale** : {rationale}\n")
        else:
            sections.append("_Not enough data for a recommendation._\n")

        report_content = "\n".join(sections)
        output_path = resolved_output_dir / f"report_{ts_filename}.md"
        output_path.write_text(report_content, encoding="utf-8")
        logger.info("Report written → %s", output_path)
        return output_path

    # ------------------------------------------------------------------
    # Table formatters
    # ------------------------------------------------------------------

    def _format_comparison_table(self, results: list[EvalResults]) -> str:
        """Build a Markdown comparison table for the standard configurations.

        Columns: Config, Recall@1, Recall@3, Recall@5, MRR, HitRate@1,
        p50 (ms), p95 (ms).

        Args:
            results: Aggregated results for each configuration.

        Returns:
            Markdown table string (including trailing newline).
        """
        header = (
            "| Config | Recall@1 | Recall@3 | Recall@5 | MRR | HitRate@1 | p50 (ms) | p95 (ms) |"
        )
        sep = "|--------|----------|----------|----------|-----|-----------|----------|----------|"
        rows = [header, sep]
        for r in results:
            rows.append(
                f"| {r.config.name} "
                f"| {r.recall_at_1:.1%} "
                f"| {r.recall_at_3:.1%} "
                f"| {r.recall_at_5:.1%} "
                f"| {r.mrr:.3f} "
                f"| {r.hit_rate_at_1:.1%} "
                f"| {r.latency_p50_ms:.0f} "
                f"| {r.latency_p95_ms:.0f} |"
            )
        return "\n".join(rows) + "\n"

    def _format_ablation_table(self, ablation_results: list[EvalResults]) -> str:
        """Build a Markdown table for the RRF k ablation results.

        Columns: k, Recall@5, MRR, Δ vs k=60.

        The baseline for the Δ column is the result whose ``rrf_k`` equals 60;
        if that exact value is absent, no delta is shown.

        Args:
            ablation_results: RRF ablation results, one per k value.

        Returns:
            Markdown table string (including trailing newline).
        """
        baseline = next((r for r in ablation_results if r.config.rrf_k == 60), None)
        header = "| k | Recall@5 | MRR | Δ vs k=60 |"
        sep = "|---|----------|-----|-----------|"
        rows = [header, sep]
        for r in ablation_results:
            if baseline is not None:
                delta = r.recall_at_5 - baseline.recall_at_5
                delta_str = f"{delta:+.1%}"
            else:
                delta_str = "—"
            rows.append(f"| {r.config.rrf_k} | {r.recall_at_5:.1%} | {r.mrr:.3f} | {delta_str} |")
        return "\n".join(rows) + "\n"

    def _format_hyde_table(self, results: list[EvalResults]) -> str:
        """Build a Markdown table comparing hybrid with and without HyDE.

        Tries to pair ``hybrid_<cat>`` with ``hybrid_hyde_<cat>`` configs.
        Falls back to listing all results individually if pairing fails.

        Args:
            results: HyDE ablation results (any ordering).

        Returns:
            Markdown table string (including trailing newline).
        """
        # Try to pair configs by category suffix
        no_hyde_map: dict[str, EvalResults] = {}
        hyde_map: dict[str, EvalResults] = {}

        for r in results:
            name = r.config.name
            if name.startswith("hybrid_hyde_"):
                category = name[len("hybrid_hyde_") :]
                hyde_map[category] = r
            elif name.startswith("hybrid_"):
                category = name[len("hybrid_") :]
                no_hyde_map[category] = r
            elif name == "hybrid":
                no_hyde_map["global"] = r
            elif name == "hybrid_hyde":
                hyde_map["global"] = r

        all_categories = sorted(set(no_hyde_map) | set(hyde_map))
        if not all_categories:
            # Fallback: list as-is
            header = "| Config | Recall@5 | MRR |"
            sep = "|--------|----------|-----|"
            rows = [header, sep]
            for r in results:
                rows.append(f"| {r.config.name} | {r.recall_at_5:.1%} | {r.mrr:.3f} |")
            return "\n".join(rows) + "\n"

        header = "| Category | Hybrid (no HyDE) | Hybrid + HyDE | Δ |"
        sep = "|----------|-----------------|---------------|---|"
        rows = [header, sep]
        for cat in all_categories:
            no_hyde_r = no_hyde_map.get(cat)
            hyde_r = hyde_map.get(cat)
            no_hyde_str = f"{no_hyde_r.recall_at_5:.1%}" if no_hyde_r else "—"
            hyde_str = f"{hyde_r.recall_at_5:.1%}" if hyde_r else "—"
            if no_hyde_r and hyde_r:
                delta = hyde_r.recall_at_5 - no_hyde_r.recall_at_5
                delta_str = f"{delta:+.1%}"
            else:
                delta_str = "—"
            rows.append(f"| {cat} | {no_hyde_str} | {hyde_str} | {delta_str} |")
        return "\n".join(rows) + "\n"

    def _format_generation_table(self, results: list[EvalResults]) -> str:
        """Build a Markdown table for generation quality metrics.

        Columns: Config, F1 Score, Answer Correctness (RAGAS), Faithfulness (RAGAS).

        Args:
            results: Results with at least one non-null generation metric.

        Returns:
            Markdown table string (including trailing newline).
        """
        header = "| Config | F1 Score | Answer Correctness | Faithfulness |"
        sep = "|--------|----------|--------------------|--------------|"
        rows = [header, sep]
        for r in results:
            f1 = f"{r.f1_score:.3f}" if r.f1_score is not None else "—"
            ac = (
                f"{r.ragas_answer_correctness:.3f}"
                if r.ragas_answer_correctness is not None
                else "—"
            )
            faith = f"{r.ragas_faithfulness:.3f}" if r.ragas_faithfulness is not None else "—"
            rows.append(f"| {r.config.name} | {f1} | {ac} | {faith} |")
        return "\n".join(rows) + "\n"

    # ------------------------------------------------------------------
    # Findings + recommendation
    # ------------------------------------------------------------------

    def _generate_findings(self, results: list[EvalResults]) -> list[str]:
        """Generate 3–5 automatic findings from the evaluation data.

        Examples of generated sentences:

        * ``"hybrid_hyde achieves Recall@5=92.0%, outperforming dense_only
          by +8.0%."``
        * ``"bm25_only has the lowest p50 latency at 45 ms."``

        Args:
            results: All loaded evaluation results (any ordering).

        Returns:
            List of finding strings (each string = one bullet point).
        """
        if not results:
            return []

        findings: list[str] = []

        standard = [r for r in results if r.config.name in _STANDARD_CONFIG_NAMES]
        rrf_ablation = sorted(
            [r for r in results if r.config.name.startswith(_RRF_PREFIX)],
            key=lambda r: r.config.rrf_k,
        )

        if standard:
            best = max(standard, key=lambda r: r.recall_at_5)
            worst = min(standard, key=lambda r: r.recall_at_5)
            delta = best.recall_at_5 - worst.recall_at_5

            findings.append(
                f"`{best.config.name}` achieves the highest Recall@5 at "
                f"{best.recall_at_5:.1%}, outperforming `{worst.config.name}` "
                f"by +{delta:.1%}."
            )

            # HyDE impact
            hybrid = next((r for r in standard if r.config.name == "hybrid"), None)
            hybrid_hyde = next((r for r in standard if r.config.name == "hybrid_hyde"), None)
            if hybrid and hybrid_hyde:
                hyde_delta = hybrid_hyde.recall_at_5 - hybrid.recall_at_5
                direction = "improves" if hyde_delta >= 0 else "reduces"
                findings.append(
                    f"HyDE expansion {direction} Recall@5 by {abs(hyde_delta):.1%} "
                    f"({hybrid.recall_at_5:.1%} → {hybrid_hyde.recall_at_5:.1%})."
                )

            # Latency leader
            fastest = min(standard, key=lambda r: r.latency_p50_ms)
            findings.append(
                f"`{fastest.config.name}` has the lowest median latency at "
                f"{fastest.latency_p50_ms:.0f} ms (p50)."
            )

            # Target check
            target = 0.85
            above_target = [r for r in standard if r.recall_at_5 >= target]
            if above_target:
                names = ", ".join(f"`{r.config.name}`" for r in above_target)
                findings.append(
                    f"{len(above_target)} configuration(s) meet the Recall@5 ≥ 85% "
                    f"target: {names}."
                )
            else:
                findings.append(
                    f"No configuration meets the Recall@5 ≥ 85% target yet "
                    f"(best: {best.recall_at_5:.1%})."
                )

        if rrf_ablation:
            best_rrf = max(rrf_ablation, key=lambda r: r.recall_at_5)
            findings.append(
                f"In the RRF k ablation, k={best_rrf.config.rrf_k} yields the highest "
                f"Recall@5 ({best_rrf.recall_at_5:.1%})."
            )

        return findings[:5]

    def _best_config(self, results: list[EvalResults]) -> str:
        """Return the configuration name with the highest Recall@5.

        Args:
            results: Aggregated evaluation results to rank.

        Returns:
            Name of the best configuration.

        Raises:
            ValueError: If *results* is empty.
        """
        if not results:
            raise ValueError("Cannot determine best config: results list is empty.")
        return max(results, key=lambda r: r.recall_at_5).config.name

    def _generate_rationale(self, best_name: str, results: list[EvalResults]) -> str:
        """Build a short auto-generated rationale for the recommended config.

        Args:
            best_name: Name of the best configuration.
            results: All standard configuration results.

        Returns:
            One-sentence rationale string.
        """
        best = next((r for r in results if r.config.name == best_name), None)
        if best is None:
            return f"`{best_name}` achieves the highest Recall@5 across all tested configurations."

        others = [r for r in results if r.config.name != best_name]
        if not others:
            return (
                f"`{best_name}` achieves Recall@5={best.recall_at_5:.1%} "
                f"with MRR={best.mrr:.3f} and p50={best.latency_p50_ms:.0f} ms."
            )

        runner_up = max(others, key=lambda r: r.recall_at_5)
        margin = best.recall_at_5 - runner_up.recall_at_5
        return (
            f"`{best_name}` achieves Recall@5={best.recall_at_5:.1%} "
            f"(+{margin:.1%} vs `{runner_up.config.name}`), "
            f"MRR={best.mrr:.3f}, p50={best.latency_p50_ms:.0f} ms."
        )

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _load_results(self, results_dir: Path) -> list[EvalResults]:
        """Load all ``eval_*.json`` files from *results_dir*.

        Files that cannot be parsed are logged at WARNING level and skipped.

        Args:
            results_dir: Directory to scan.

        Returns:
            List of deserialized :class:`~evaluation.harness.EvalResults`.
        """
        loaded: list[EvalResults] = []
        json_files = sorted(results_dir.glob("eval_*.json"))
        logger.info("Found %d result file(s) in %s", len(json_files), results_dir)
        for path in json_files:
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                loaded.append(_results_from_dict(data))
                logger.debug("Loaded %s", path.name)
            except (json.JSONDecodeError, KeyError, TypeError) as exc:
                logger.warning("Skipping %s — parse error: %s", path.name, exc)
        return loaded

    def _extract_hyde_pairs_from_standard(self, results: list[EvalResults]) -> list[EvalResults]:
        """Extract HyDE-relevant results from the standard configuration set.

        Returns ``[hybrid, hybrid_hyde]`` when both are present, otherwise
        an empty list.

        Args:
            results: Standard configuration results.

        Returns:
            Filtered list for HyDE comparison.
        """
        hybrid = next((r for r in results if r.config.name == "hybrid"), None)
        hybrid_hyde = next((r for r in results if r.config.name == "hybrid_hyde"), None)
        if hybrid and hybrid_hyde:
            return [hybrid, hybrid_hyde]
        return []


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------


def _main() -> None:
    """Generate a Markdown report from existing evaluation results."""
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s  %(levelname)-8s  %(name)s  %(message)s",
    )
    results_dir = Path("evaluation/results")
    output_dir = Path("evaluation/reports")

    generator = ReportGenerator()
    try:
        report_path = generator.generate(results_dir=results_dir, output_dir=output_dir)
        print(f"Report generated → {report_path}")
    except (FileNotFoundError, ValueError) as exc:
        logger.error("%s", exc)


if __name__ == "__main__":
    _main()
