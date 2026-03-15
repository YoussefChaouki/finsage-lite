"""Inspect PatronusAI/financebench dataset and recommend benchmark corpus.

Usage:
    python scripts/inspect_financebench.py
"""

from __future__ import annotations

import logging
import re
import sys
from collections import Counter
from typing import Any

logging.basicConfig(level=logging.INFO, format="%(message)s")
logger = logging.getLogger(__name__)


def _require_datasets() -> Any:
    """Import and return the ``datasets`` module, exiting with a clear message if missing.

    Returns:
        The ``datasets`` module object.
    """
    try:
        import datasets  # noqa: PLC0415

        return datasets
    except ImportError:
        logger.error("The 'datasets' package is not installed. Run:\n  pip install datasets")
        sys.exit(1)


def _section(title: str) -> None:
    """Log a formatted section header.

    Args:
        title: Section title to display.
    """
    logger.info("\n%s", "=" * 60)
    logger.info("  %s", title)
    logger.info("%s", "=" * 60)


def _display_counter(counter: Counter[str], label: str, top_n: int = 20) -> None:
    """Log the top-N entries of a Counter in descending order.

    Args:
        counter: Counter mapping string keys to integer counts.
        label: Header label printed above the table.
        top_n: Maximum number of entries to display.
    """
    logger.info("\n%s (top %d):", label, top_n)
    for value, count in counter.most_common(top_n):
        logger.info("  %-40s %3d", value, count)


def _normalise_company(raw: str) -> str:
    """Return a stripped canonical name from the raw company string.

    Args:
        raw: Raw company string as it appears in the dataset.

    Returns:
        Stripped company name.
    """
    return raw.strip()


def _normalise_year(raw: Any) -> str:
    """Extract a 4-digit fiscal year from an arbitrary field value.

    Args:
        raw: Raw field value; may be an int, float, or string.

    Returns:
        4-digit year string if found, otherwise the stringified input.
    """
    text = str(raw).strip()
    m = re.search(r"\b(20\d{2})\b", text)
    return m.group(1) if m else text


def _select_benchmark_companies(
    company_year_counts: dict[tuple[str, str], int],
    company_counts: Counter[str],
    target_companies: int = 4,
) -> list[tuple[str, str, int]]:
    """Select companies that maximise question coverage with minimum filings.

    Strategy:
    1. Pick the top-N companies by total question count.
    2. For each chosen company, keep only its most-represented fiscal year
       (one filing per company minimises ingestion effort).

    Args:
        company_year_counts: Mapping of ``(company, fiscal_year)`` to question count.
        company_counts: Aggregate question count per company.
        target_companies: Number of companies to select.

    Returns:
        List of ``(company, fiscal_year, question_count)`` tuples, sorted by
        question count descending.
    """
    top_companies = [c for c, _ in company_counts.most_common(target_companies)]

    selected: list[tuple[str, str, int]] = []
    for company in top_companies:
        # Find best year for this company
        year_counts: Counter[str] = Counter(
            {year: count for (comp, year), count in company_year_counts.items() if comp == company}
        )
        best_year, count = year_counts.most_common(1)[0]
        selected.append((company, best_year, count))

    return sorted(selected, key=lambda x: x[2], reverse=True)


def main() -> None:
    """Load financebench, print statistics, and recommend a benchmark corpus."""
    datasets = _require_datasets()

    _section("Loading PatronusAI/financebench")
    logger.info("Downloading dataset from HuggingFace Hub …")
    ds = datasets.load_dataset("PatronusAI/financebench", split="train", trust_remote_code=True)
    logger.info("Dataset loaded ✓")

    # ------------------------------------------------------------------ schema
    _section("Available columns")
    for col in ds.column_names:
        logger.info("  • %s", col)

    # ------------------------------------------------------------------ totals
    total = len(ds)
    _section(f"Total questions: {total}")

    # ------------------------------------------------------------------ company
    # Try common field names
    company_field: str | None = None
    for candidate in ("company", "company_name", "ticker", "symbol"):
        if candidate in ds.column_names:
            company_field = candidate
            break

    year_field: str | None = None
    for candidate in ("fiscal_year", "year", "fy", "period", "doc_year", "filing_year"):
        if candidate in ds.column_names:
            year_field = candidate
            break

    category_field: str | None = None
    for candidate in ("question_type", "category", "difficulty", "domain", "type"):
        if candidate in ds.column_names:
            category_field = candidate
            break

    if company_field is None:
        logger.warning("No company column found; tried: company, company_name, ticker, symbol")
        # Try to infer from doc_name / doc_id
        for candidate in ("doc_name", "document", "filename", "doc_id"):
            if candidate in ds.column_names:
                logger.info("  → Will approximate company from '%s'", candidate)
                company_field = candidate
                break

    # Build counters
    company_counts: Counter[str] = Counter()
    year_counts: Counter[str] = Counter()
    company_year_counts: dict[tuple[str, str], int] = {}
    category_counts: Counter[str] = Counter()

    for row in ds:
        company_raw = str(row.get(company_field, "UNKNOWN")) if company_field else "UNKNOWN"
        company = _normalise_company(company_raw)
        company_counts[company] += 1

        if year_field:
            year = _normalise_year(row.get(year_field, ""))
            year_counts[year] += 1
            key = (company, year)
            company_year_counts[key] = company_year_counts.get(key, 0) + 1

        if category_field:
            cat = str(row.get(category_field, "UNKNOWN"))
            category_counts[cat] += 1

    _display_counter(company_counts, "Questions per company")

    if year_counts:
        _display_counter(year_counts, "Questions per fiscal year")
    else:
        logger.info("\n(No fiscal year column detected)")

    if category_counts:
        _display_counter(category_counts, "Questions per category/difficulty")
    else:
        logger.info("\n(No category/difficulty column detected)")

    # --------------------------------------------------------- recommendation
    _section("Benchmark corpus recommendation")
    logger.info("Criteria: max question coverage, min filings to ingest (1 filing/company)")
    logger.info("Target: 3–4 companies\n")

    if company_year_counts:
        selected = _select_benchmark_companies(
            company_year_counts, company_counts, target_companies=4
        )
        total_questions = sum(c for _, _, c in selected)
        coverage_pct = 100 * total_questions / total if total else 0

        logger.info("Selected companies (best fiscal year per company):")
        for company, year, count in selected:
            logger.info("  %-35s FY%s  →  %3d questions", company, year, count)

        logger.info(
            "\nTotal questions covered: %d / %d  (%.1f%%)", total_questions, total, coverage_pct
        )

        summary_parts = [f"{company} FY{year}" for company, year, _ in selected]
        logger.info("\nRetenir : [%s]", ", ".join(summary_parts))
    else:
        # Fallback: company only
        selected_companies = [c for c, _ in company_counts.most_common(4)]
        logger.info("(No fiscal year data — selecting by company only)")
        logger.info("Retenir : [%s]", ", ".join(selected_companies))


if __name__ == "__main__":
    main()
