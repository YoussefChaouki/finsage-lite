"""Tests for ReportGenerator.

Verifies that the generator produces a well-formed Markdown report from
synthetic EvalResults fixtures stored as JSON in a temporary directory.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from evaluation.harness import EvalResults, QuestionResult
from evaluation.report_generator import ReportGenerator
from evaluation.schemas import EvalConfig

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------

_CONFIGS = [
    EvalConfig(name="dense_only", retrieval_mode="dense", hyde_enabled=False),
    EvalConfig(name="bm25_only", retrieval_mode="bm25", hyde_enabled=False),
    EvalConfig(name="hybrid", retrieval_mode="hybrid", rrf_k=60, hyde_enabled=False),
    EvalConfig(name="hybrid_hyde", retrieval_mode="hybrid", rrf_k=60, hyde_enabled=True),
]

_RECALL_VALUES = [0.60, 0.65, 0.80, 0.88]


def _make_question_results(config_name: str, n: int = 5) -> list[QuestionResult]:
    return [
        QuestionResult(
            question_id=i,
            question=f"Q{i}?",
            config_name=config_name,
            retrieved_chunk_ids=[str(j) for j in range(1, 6)],
            gold_found=True,
            gold_rank=1,
            latency_ms=50.0 + i,
        )
        for i in range(n)
    ]


def _make_eval_results(config: EvalConfig, recall: float) -> EvalResults:
    return EvalResults(
        config=config,
        recall_at_1=recall * 0.6,
        recall_at_3=recall * 0.85,
        recall_at_5=recall,
        mrr=recall * 0.75,
        hit_rate_at_1=recall * 0.6,
        hit_rate_at_3=recall * 0.85,
        hit_rate_at_5=recall,
        latency_p50_ms=100.0,
        latency_p95_ms=250.0,
        latency_p99_ms=400.0,
        n_questions=10,
        per_question=_make_question_results(config.name),
        f1_score=0.72 if config.name == "hybrid_hyde" else None,
    )


@pytest.fixture()
def results_dir(tmp_path: Path) -> Path:
    """Write synthetic EvalResults JSON files to a temp directory."""
    rdir = tmp_path / "results"
    rdir.mkdir()
    for config, recall in zip(_CONFIGS, _RECALL_VALUES, strict=True):
        result = _make_eval_results(config, recall)
        data = result.to_dict()
        (rdir / f"eval_{config.name}_20260101_000000.json").write_text(
            json.dumps(data, indent=2), encoding="utf-8"
        )
    return rdir


@pytest.fixture()
def output_dir(tmp_path: Path) -> Path:
    d = tmp_path / "reports"
    d.mkdir()
    return d


@pytest.fixture()
def generator() -> ReportGenerator:
    return ReportGenerator()


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


def test_report_file_created(
    generator: ReportGenerator, results_dir: Path, output_dir: Path
) -> None:
    """generate() must create a .md file in output_dir."""
    report_path = generator.generate(results_dir=results_dir, output_dir=output_dir)

    assert report_path.exists(), "Report file was not created"
    assert report_path.suffix == ".md", f"Expected .md extension, got {report_path.suffix}"
    assert report_path.parent == output_dir


def test_report_contains_sections(
    generator: ReportGenerator, results_dir: Path, output_dir: Path
) -> None:
    """Generated report must contain all expected H2 section headers."""
    report_path = generator.generate(results_dir=results_dir, output_dir=output_dir)
    content = report_path.read_text(encoding="utf-8")

    expected_headers = [
        "## 1. Configuration Comparison",
        "## 2. RRF k Ablation",
        "## 3. HyDE Impact",
        "## 4. Generation Quality",
        "## 5. Key Findings",
        "## 6. Recommendation",
    ]
    for header in expected_headers:
        assert header in content, f"Missing section header: {header!r}"


def test_report_not_empty(generator: ReportGenerator, results_dir: Path, output_dir: Path) -> None:
    """Generated report must be at least 500 characters long."""
    report_path = generator.generate(results_dir=results_dir, output_dir=output_dir)
    content = report_path.read_text(encoding="utf-8")

    assert len(content) >= 500, f"Report too short: {len(content)} chars (expected >= 500)"


def test_findings_generated(
    generator: ReportGenerator, results_dir: Path, output_dir: Path
) -> None:
    """Key Findings section must contain at least one bullet point."""
    report_path = generator.generate(results_dir=results_dir, output_dir=output_dir)
    content = report_path.read_text(encoding="utf-8")

    findings_start = content.find("## 5. Key Findings")
    assert findings_start != -1, "Key Findings section not found"

    # Extract section content up to next H2
    findings_section = content[findings_start:]
    next_section = findings_section.find("\n## ", 1)
    if next_section != -1:
        findings_section = findings_section[:next_section]

    assert "- " in findings_section, "Key Findings section contains no bullet points"


def test_report_missing_results_dir_raises(generator: ReportGenerator, tmp_path: Path) -> None:
    """generate() must raise FileNotFoundError for a non-existent results dir."""
    with pytest.raises(FileNotFoundError):
        generator.generate(results_dir=tmp_path / "nonexistent")


def test_report_empty_results_dir_raises(generator: ReportGenerator, tmp_path: Path) -> None:
    """generate() must raise ValueError when no eval_*.json files are found."""
    empty_dir = tmp_path / "empty"
    empty_dir.mkdir()
    with pytest.raises(ValueError, match="No valid eval_.*json files found"):
        generator.generate(results_dir=empty_dir)


def test_format_ablation_table_with_rrf_results(generator: ReportGenerator) -> None:
    """_format_ablation_table must include a delta column relative to k=60."""
    rrf_results = []
    for k in [10, 30, 60, 100]:
        config = EvalConfig(name=f"hybrid_rrf_k{k}", retrieval_mode="hybrid", rrf_k=k)
        rrf_results.append(_make_eval_results(config, recall=0.70 + k * 0.001))

    table = generator._format_ablation_table(rrf_results)

    assert "Δ vs k=60" in table
    assert "| 60 |" in table
    assert "+0.0%" in table or "0.0%" in table  # k=60 row has Δ=0


def test_best_config_returns_highest_recall(generator: ReportGenerator) -> None:
    """_best_config must return the config name with the highest Recall@5."""
    results = [
        _make_eval_results(config, recall)
        for config, recall in zip(_CONFIGS, _RECALL_VALUES, strict=True)
    ]
    best = generator._best_config(results)
    assert best == "hybrid_hyde"  # recall=0.88 is highest


def test_best_config_raises_on_empty(generator: ReportGenerator) -> None:
    with pytest.raises(ValueError):
        generator._best_config([])
