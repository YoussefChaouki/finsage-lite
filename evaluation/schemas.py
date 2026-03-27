"""Pydantic v2 schemas for the evaluation harness."""

from __future__ import annotations

from pydantic import BaseModel


class EvalQuestion(BaseModel):
    """Single evaluation question parsed from FinanceBench.

    Attributes:
        question: The question text.
        expected_answer: The ground-truth answer.
        evidence_text: Supporting evidence passage, if available.
        company: Company ticker or name (e.g. ``"AAPL"``).
        fiscal_year: Fiscal year as an integer (e.g. ``2022``).
        difficulty: Difficulty label (e.g. ``"easy"`` / ``"hard"``), if available.
        category: Question category (e.g. ``"table"`` / ``"text"``), if available.
        source_file: Filing document name or path, if available.
    """

    question: str
    expected_answer: str
    evidence_text: str | None = None
    company: str
    fiscal_year: int
    difficulty: str | None = None
    category: str | None = None
    source_file: str | None = None


class EvalConfig(BaseModel):
    """Configuration for a single retrieval evaluation run.

    Attributes:
        name: Human-readable label (e.g. ``"hybrid_hyde"``).
        retrieval_mode: Retrieval strategy: ``"dense"``, ``"bm25"``, or ``"hybrid"``.
        top_k: Number of chunks to retrieve.
        rrf_k: RRF constant *k* (default 60).
        hyde_enabled: Whether to apply HyDE query expansion.
    """

    name: str
    retrieval_mode: str  # "dense" | "bm25" | "hybrid"
    top_k: int = 5
    rrf_k: int = 60
    hyde_enabled: bool = False
