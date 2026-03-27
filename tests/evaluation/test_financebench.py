"""Tests for FinanceBenchLoader and EvalQuestion / EvalConfig schemas."""

from __future__ import annotations

import sys
from typing import Any
from unittest.mock import MagicMock, patch

import pytest
from evaluation.datasets.financebench import FinanceBenchLoader
from evaluation.schemas import EvalConfig, EvalQuestion

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


class _MockDataset:
    """Minimal in-memory stand-in for a HuggingFace Dataset."""

    def __init__(self, rows: list[dict[str, Any]]) -> None:
        self._rows = rows
        self.column_names: list[str] = list(rows[0].keys()) if rows else []

    def __len__(self) -> int:
        return len(self._rows)

    def __iter__(self) -> Any:
        return iter(self._rows)


def _make_datasets_mock(rows: list[dict[str, Any]]) -> MagicMock:
    """Return a MagicMock that mimics the ``datasets`` module."""
    mock = MagicMock()
    mock.load_dataset.return_value = _MockDataset(rows)
    return mock


def _row(
    question: str = "What is Apple's total revenue?",
    answer: str = "$394 billion",
    justification: str = "Total net sales were $394.3 billion.",
    company: str = "Apple",
    doc_period_of_report: str = "FY2022",
    question_type: str = "RETRIEVABLE",
    doc_name: str = "Apple_2022_10K",
) -> dict[str, Any]:
    """Build a minimal dataset row dict."""
    return {
        "question": question,
        "answer": answer,
        "justification": justification,
        "company": company,
        "doc_period_of_report": doc_period_of_report,
        "question_type": question_type,
        "doc_name": doc_name,
    }


SAMPLE_ROWS: list[dict[str, Any]] = [
    _row(),
    _row(
        question="Describe Apple's main risk factors.",
        answer="Market saturation and supply-chain disruptions.",
        question_type="COMPLEX",
    ),
    _row(
        question="What is Microsoft's operating income?",
        answer="$88 billion",
        justification="Operating income totalled $88.5 billion.",
        company="Microsoft",
        doc_period_of_report="FY2023",
        question_type="RETRIEVABLE",
        doc_name="MSFT_2023_10K",
    ),
]


# ---------------------------------------------------------------------------
# Schema smoke tests
# ---------------------------------------------------------------------------


def test_eval_question_construction() -> None:
    """EvalQuestion can be constructed with mandatory fields only."""
    q = EvalQuestion(question="Q?", expected_answer="A", company="AAPL", fiscal_year=2022)
    assert q.evidence_text is None
    assert q.difficulty is None
    assert q.category is None
    assert q.source_file is None


def test_eval_config_defaults() -> None:
    """EvalConfig default values match the spec."""
    cfg = EvalConfig(name="baseline", retrieval_mode="hybrid")
    assert cfg.top_k == 5
    assert cfg.rrf_k == 60
    assert cfg.hyde_enabled is False


# ---------------------------------------------------------------------------
# Loader tests
# ---------------------------------------------------------------------------


def test_load_no_filter() -> None:
    """load() with no filters returns all parseable questions."""
    loader = FinanceBenchLoader()
    with patch.dict(sys.modules, {"datasets": _make_datasets_mock(SAMPLE_ROWS)}):
        questions = loader.load()
    assert len(questions) == len(SAMPLE_ROWS)


def test_load_filtered_by_company() -> None:
    """load(companies=[...]) keeps only rows whose company matches."""
    loader = FinanceBenchLoader()
    with patch.dict(sys.modules, {"datasets": _make_datasets_mock(SAMPLE_ROWS)}):
        questions = loader.load(companies=["Apple"])
    assert len(questions) == 2
    assert all(q.company == "Apple" for q in questions)


def test_load_filtered_by_year() -> None:
    """load(years=[...]) keeps only rows whose fiscal_year matches."""
    loader = FinanceBenchLoader()
    with patch.dict(sys.modules, {"datasets": _make_datasets_mock(SAMPLE_ROWS)}):
        questions = loader.load(years=[2023])
    assert len(questions) == 1
    assert questions[0].fiscal_year == 2023


def test_load_filtered_by_company_and_year() -> None:
    """Combined company + year filter is applied as AND."""
    loader = FinanceBenchLoader()
    with patch.dict(sys.modules, {"datasets": _make_datasets_mock(SAMPLE_ROWS)}):
        questions = loader.load(companies=["Apple"], years=[2022])
    assert len(questions) == 2
    assert all(q.company == "Apple" and q.fiscal_year == 2022 for q in questions)


def test_eval_question_fields() -> None:
    """All mandatory EvalQuestion fields are present and correctly typed."""
    loader = FinanceBenchLoader()
    with patch.dict(sys.modules, {"datasets": _make_datasets_mock(SAMPLE_ROWS)}):
        questions = loader.load()

    assert questions, "Expected at least one question"
    q = questions[0]
    assert isinstance(q.question, str) and q.question
    assert isinstance(q.expected_answer, str) and q.expected_answer
    assert isinstance(q.company, str) and q.company
    assert isinstance(q.fiscal_year, int)
    assert q.evidence_text is None or isinstance(q.evidence_text, str)
    assert q.difficulty is None or isinstance(q.difficulty, str)
    assert q.category is None or isinstance(q.category, str)
    assert q.source_file is None or isinstance(q.source_file, str)


def test_stats_keys() -> None:
    """stats() returns a dict with the four expected top-level keys."""
    loader = FinanceBenchLoader()
    with patch.dict(sys.modules, {"datasets": _make_datasets_mock(SAMPLE_ROWS)}):
        questions = loader.load()

    result = loader.stats(questions)
    assert "total" in result
    assert "by_company" in result
    assert "by_category" in result
    assert "by_difficulty" in result
    assert result["total"] == len(questions)


def test_stats_by_company_counts() -> None:
    """stats() correctly counts questions per company."""
    loader = FinanceBenchLoader()
    with patch.dict(sys.modules, {"datasets": _make_datasets_mock(SAMPLE_ROWS)}):
        questions = loader.load()

    result = loader.stats(questions)
    assert result["by_company"]["Apple"] == 2
    assert result["by_company"]["Microsoft"] == 1


def test_load_skips_rows_with_missing_fields() -> None:
    """Rows missing question or answer are silently skipped."""
    broken_rows = [
        {"question": "", "answer": "A", "company": "AAPL", "doc_period_of_report": "FY2022"},
        {"question": "Q?", "answer": "", "company": "AAPL", "doc_period_of_report": "FY2022"},
        _row(),  # one valid row
    ]
    loader = FinanceBenchLoader()
    with patch.dict(sys.modules, {"datasets": _make_datasets_mock(broken_rows)}):
        questions = loader.load()
    assert len(questions) == 1


def test_load_infers_company_from_doc_name() -> None:
    """When no 'company' column exists, company is inferred from doc_name."""
    rows = [
        {
            "question": "What is revenue?",
            "answer": "$100B",
            "doc_name": "GOOGL_2022_10K",
            "doc_period_of_report": "FY2022",
        }
    ]
    loader = FinanceBenchLoader()
    with patch.dict(sys.modules, {"datasets": _make_datasets_mock(rows)}):
        questions = loader.load()
    assert len(questions) == 1
    assert questions[0].company == "GOOGL"


def test_stats_empty_list() -> None:
    """stats() on an empty list returns zeros and empty dicts."""
    loader = FinanceBenchLoader()
    result = loader.stats([])
    assert result["total"] == 0
    assert result["by_company"] == {}
    assert result["by_category"] == {}
    assert result["by_difficulty"] == {}


def test_column_map_documented() -> None:
    """COLUMN_MAP is a non-empty dict of str→str entries."""
    assert isinstance(FinanceBenchLoader.COLUMN_MAP, dict)
    assert FinanceBenchLoader.COLUMN_MAP
    assert all(
        isinstance(k, str) and isinstance(v, str) for k, v in FinanceBenchLoader.COLUMN_MAP.items()
    )


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        ("FY2022", 2022),
        ("2023", 2023),
        ("fiscal year 2021", 2021),
        ("no year here", None),
        (2024, 2024),
    ],
)
def test_extract_year(raw: Any, expected: int | None) -> None:
    """_extract_year correctly parses various raw year formats."""
    loader = FinanceBenchLoader()
    assert loader._extract_year(raw) == expected
