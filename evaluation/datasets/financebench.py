"""FinanceBench dataset loader for the evaluation harness."""

from __future__ import annotations

import logging
import re
import sys
from collections import Counter
from typing import Any

from evaluation.schemas import EvalQuestion

logger = logging.getLogger(__name__)


class FinanceBenchLoader:
    """Load and filter the PatronusAI/financebench dataset.

    The dataset is downloaded lazily from HuggingFace Hub on the first call
    to :meth:`load`.  Each row is parsed into a typed :class:`EvalQuestion`
    instance; rows with missing mandatory fields are silently skipped.

    The ``COLUMN_MAP`` documents the expected HuggingFace column names and
    their mapping to :class:`EvalQuestion` field names.  The parsing logic
    also falls back to several alternative column names to handle minor
    dataset schema variations.
    """

    COLUMN_MAP: dict[str, str] = {
        "question": "question",
        "answer": "expected_answer",
        "justification": "evidence_text",
        "company": "company",
        "doc_period_of_report": "fiscal_year",
        "question_type": "category",
        "doc_name": "source_file",
    }

    # ------------------------------------------------------------------ private

    def _require_datasets(self) -> Any:
        """Import and return the ``datasets`` module.

        Returns:
            The ``datasets`` module object.

        Raises:
            SystemExit: If the package is not installed.
        """
        try:
            import datasets  # noqa: PLC0415

            return datasets
        except ImportError:
            logger.error("The 'datasets' package is not installed. Run: pip install datasets")
            sys.exit(1)

    def _extract_year(self, raw: Any) -> int | None:
        """Extract a 4-digit fiscal year from an arbitrary value.

        Args:
            raw: Raw field value; may be an int, float, or string.

        Returns:
            Integer year, or ``None`` if no 4-digit year is found.
        """
        text = str(raw).strip()
        # Use lookaround instead of \b: word-boundary doesn't fire between a
        # letter and a digit, so "FY2022" would not be matched by \b(20\d{2})\b.
        match = re.search(r"(?<!\d)(20\d{2})(?!\d)", text)
        return int(match.group(1)) if match else None

    def _company_from_doc_name(self, doc_name: str) -> str:
        """Infer a company name from a document filename.

        Takes everything before the first underscore
        (e.g. ``"Apple_2022_10K"`` → ``"Apple"``).

        Args:
            doc_name: Raw document filename from the dataset.

        Returns:
            Inferred company string.
        """
        return doc_name.split("_")[0] if "_" in doc_name else doc_name

    def _parse_row(self, row: dict[str, Any], columns: list[str]) -> EvalQuestion | None:
        """Parse a single HuggingFace dataset row into an :class:`EvalQuestion`.

        Args:
            row: Raw dataset row as a plain dict.
            columns: Column names present in the dataset (used for existence checks).

        Returns:
            Parsed question, or ``None`` if mandatory fields are absent.
        """
        question = str(row.get("question", "")).strip()
        expected_answer = str(row.get("answer", "")).strip()
        if not question or not expected_answer:
            return None

        # evidence_text — try several alternative column names
        evidence_text: str | None = None
        for col in ("justification", "evidence", "context"):
            if col in columns:
                val = str(row.get(col, "")).strip()
                if val:
                    evidence_text = val
                    break

        # company — direct columns first, then infer from doc_name
        company = ""
        for col in ("company", "company_name", "ticker", "symbol"):
            if col in columns:
                val = str(row.get(col, "")).strip()
                if val:
                    company = val
                    break
        if not company:
            for col in ("doc_name", "document", "filename"):
                if col in columns:
                    val = str(row.get(col, "")).strip()
                    if val:
                        company = self._company_from_doc_name(val)
                        break
        if not company:
            return None

        # fiscal_year — year columns first, then doc_name
        fiscal_year: int | None = None
        for col in ("doc_period_of_report", "fiscal_year", "year", "fy", "period", "doc_year"):
            if col in columns:
                fiscal_year = self._extract_year(row.get(col, ""))
                if fiscal_year:
                    break
        if not fiscal_year:
            if "doc_name" in columns:
                fiscal_year = self._extract_year(row.get("doc_name", ""))
        if not fiscal_year:
            return None

        # category
        category: str | None = None
        for col in ("question_type", "category", "domain", "type"):
            if col in columns:
                val = str(row.get(col, "")).strip()
                if val:
                    category = val
                    break

        # difficulty
        difficulty: str | None = None
        if "difficulty" in columns:
            val = str(row.get("difficulty", "")).strip()
            difficulty = val if val else None

        # source_file
        source_file: str | None = None
        for col in ("doc_name", "filename", "document"):
            if col in columns:
                val = str(row.get(col, "")).strip()
                if val:
                    source_file = val
                    break

        return EvalQuestion(
            question=question,
            expected_answer=expected_answer,
            evidence_text=evidence_text,
            company=company,
            fiscal_year=fiscal_year,
            difficulty=difficulty,
            category=category,
            source_file=source_file,
        )

    # ------------------------------------------------------------------ public

    def load(
        self,
        companies: list[str] | None = None,
        years: list[int] | None = None,
    ) -> list[EvalQuestion]:
        """Load FinanceBench from HuggingFace Hub and return filtered questions.

        Args:
            companies: Whitelist of company names or tickers.
                       ``None`` includes all companies.
            years: Whitelist of fiscal years (e.g. ``[2022, 2023]``).
                   ``None`` includes all years.

        Returns:
            List of parsed and filtered :class:`EvalQuestion` instances,
            in dataset order.
        """
        datasets = self._require_datasets()
        logger.info("Loading PatronusAI/financebench from HuggingFace Hub …")
        ds = datasets.load_dataset(
            "PatronusAI/financebench", split="train", trust_remote_code=True
        )
        logger.info("Dataset loaded: %d rows", len(ds))

        columns: list[str] = list(ds.column_names)
        questions: list[EvalQuestion] = []
        skipped = 0

        for raw_row in ds:
            eq = self._parse_row(dict(raw_row), columns)
            if eq is None:
                skipped += 1
                continue
            if companies is not None and eq.company not in companies:
                continue
            if years is not None and eq.fiscal_year not in years:
                continue
            questions.append(eq)

        if skipped:
            logger.warning("Skipped %d rows with missing required fields", skipped)
        logger.info("Returned %d questions after filtering", len(questions))
        return questions

    def stats(self, questions: list[EvalQuestion]) -> dict[str, Any]:
        """Compute summary statistics over a list of evaluation questions.

        Args:
            questions: Questions to analyse.

        Returns:
            Dict with keys:

            - ``total`` (int): total number of questions.
            - ``by_company`` (dict): question count per company, sorted by frequency.
            - ``by_category`` (dict): question count per category, sorted by frequency.
            - ``by_difficulty`` (dict): question count per difficulty, sorted by frequency.
        """
        by_company: Counter[str] = Counter()
        by_category: Counter[str] = Counter()
        by_difficulty: Counter[str] = Counter()

        for q in questions:
            by_company[q.company] += 1
            if q.category:
                by_category[q.category] += 1
            if q.difficulty:
                by_difficulty[q.difficulty] += 1

        return {
            "total": len(questions),
            "by_company": dict(by_company.most_common()),
            "by_category": dict(by_category.most_common()),
            "by_difficulty": dict(by_difficulty.most_common()),
        }
