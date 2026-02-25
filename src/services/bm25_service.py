"""
BM25 Sparse Retrieval Service

In-memory BM25 index over all document chunks, built once at application
startup. Provides tokenisation, index construction, and scored retrieval
with post-retrieval filtering.
"""

from __future__ import annotations

import logging
import re
import uuid
from dataclasses import dataclass
from typing import Any

import numpy as np
from rank_bm25 import BM25Okapi
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.core.exceptions import IndexNotBuiltError
from src.models.chunk import SectionType
from src.repositories.chunk import ChunkRepository
from src.schemas.search import SearchFilters, SparseResult

logger = logging.getLogger(__name__)

# ---------------------------------------------------------------------------
# Tokeniser
# ---------------------------------------------------------------------------

_STOPWORDS: frozenset[str] = frozenset(
    {
        "a",
        "an",
        "the",
        "and",
        "or",
        "but",
        "in",
        "on",
        "at",
        "to",
        "for",
        "of",
        "with",
        "by",
        "from",
        "up",
        "as",
        "into",
        "through",
        "during",
        "is",
        "are",
        "was",
        "were",
        "be",
        "been",
        "being",
        "have",
        "has",
        "had",
        "do",
        "does",
        "did",
        "will",
        "would",
        "could",
        "should",
        "may",
        "might",
        "shall",
        "can",
        "that",
        "this",
        "these",
        "those",
        "it",
        "its",
        "we",
        "our",
        "ours",
        "you",
        "your",
        "yours",
        "he",
        "she",
        "they",
        "them",
        "their",
        "theirs",
        "i",
        "me",
        "my",
        "mine",
        "what",
        "which",
        "who",
        "whom",
        "where",
        "when",
        "why",
        "how",
        "all",
        "each",
        "every",
        "both",
        "more",
        "most",
        "other",
        "some",
        "such",
        "no",
        "not",
        "only",
        "same",
        "so",
        "than",
        "too",
        "very",
        "just",
        "about",
        "above",
        "after",
        "before",
        "between",
        "also",
        "if",
        "then",
        "there",
        "here",
        "any",
        "under",
        "over",
        "while",
        "since",
        "per",
        "via",
        "upon",
    }
)


def tokenize_for_bm25(text: str) -> list[str]:
    """Tokenise text for BM25 indexing.

    Applies lowercase normalisation and alphanumeric tokenisation. No stemming
    is applied so financial terms (EBITDA, goodwill, ASC 606) remain intact.

    Args:
        text: Input text to tokenise.

    Returns:
        List of lowercase tokens with stopwords and single-character tokens
        removed. Tokens may contain hyphens (e.g. ``mark-to-market``).
    """
    lowered = text.lower()
    tokens = re.findall(r"\b[a-z0-9][a-z0-9-]*\b", lowered)
    return [t for t in tokens if t not in _STOPWORDS and len(t) > 1]


# ---------------------------------------------------------------------------
# Internal data structure
# ---------------------------------------------------------------------------


@dataclass(frozen=True, slots=True)
class _ChunkEntry:
    """Lightweight in-memory record mirroring one indexed chunk."""

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content_raw: str
    section: SectionType
    section_title: str
    metadata: dict[str, Any]
    fiscal_year: int
    company_name: str
    ticker: str


# ---------------------------------------------------------------------------
# BM25Service
# ---------------------------------------------------------------------------


class BM25Service:
    """In-memory BM25 sparse retrieval index over all document chunks.

    The service is intended to be used as a **singleton** held in
    ``app.state``. The index is built once at startup via :meth:`build_index`
    and rebuilt on demand (e.g. after new documents are ingested) by calling
    that method again.

    Filtering (by document_id, section, fiscal_year, company) is applied
    **post-retrieval**: BM25 scores all indexed chunks, then the top candidates
    are filtered in Python so no extra DB round-trip is required.
    """

    def __init__(self) -> None:
        self._index: BM25Okapi | None = None
        self._chunk_ids: list[uuid.UUID] = []
        self._entries: list[_ChunkEntry] = []
        self._is_built: bool = False
        self._document_count: int = 0

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def build_index(self, db: AsyncSession) -> None:
        """Build the BM25 index from all chunks currently in the database.

        Fetches chunk content and document metadata, tokenises each
        ``content_raw``, and constructs a :class:`rank_bm25.BM25Okapi` index.
        The parallel ``chunk_id`` → index-position mapping is stored in
        :attr:`_chunk_ids` for result retrieval. Calling this method a second
        time replaces the existing index atomically.

        Args:
            db: Async SQLAlchemy session scoped to the current startup context.
        """
        repo = ChunkRepository(db)
        rows = await repo.get_all_for_bm25()

        if not rows:
            logger.warning("build_index: no chunks found — BM25 index is empty")
            self._index = None
            self._chunk_ids = []
            self._entries = []
            self._is_built = True
            self._document_count = 0
            return

        corpus: list[list[str]] = []
        entries: list[_ChunkEntry] = []

        for row in rows:
            tokens = tokenize_for_bm25(row.content_raw)
            corpus.append(tokens)
            entries.append(
                _ChunkEntry(
                    chunk_id=row.chunk_id,
                    document_id=row.document_id,
                    content_raw=row.content_raw,
                    section=row.section,
                    section_title=row.section_title or "",
                    metadata=row.metadata or {},
                    fiscal_year=row.fiscal_year,
                    company_name=row.company_name,
                    ticker=row.ticker,
                )
            )

        self._index = BM25Okapi(corpus, k1=settings.BM25_K1, b=settings.BM25_B)
        self._chunk_ids = [e.chunk_id for e in entries]
        self._entries = entries
        self._is_built = True
        self._document_count = len({e.document_id for e in entries})

        logger.info(
            "BM25 index built: %d chunks across %d documents",
            len(entries),
            self._document_count,
        )

    async def search(
        self,
        query: str,
        top_k: int,
        filters: SearchFilters,
    ) -> list[SparseResult]:
        """Search the BM25 index for the most relevant chunks.

        Tokenises the query, scores all indexed chunks with BM25, then applies
        post-retrieval filtering. Results are ranked by BM25 score descending
        and capped at ``top_k`` after filtering.

        Args:
            query: Natural language search query (must not be empty).
            top_k: Maximum number of results to return after filtering.
            filters: Post-retrieval filter criteria (document_id, sections,
                fiscal_year, company).

        Returns:
            List of :class:`~src.schemas.search.SparseResult` objects sorted
            by ``bm25_score`` descending. ``rank`` is 1-based.

        Raises:
            IndexNotBuiltError: If :meth:`build_index` has not been called.
            ValueError: If *query* is empty or whitespace-only.
        """
        if not self._is_built:
            raise IndexNotBuiltError("BM25 index has not been built. Call build_index() first.")

        if not query.strip():
            raise ValueError("Query must not be empty or whitespace")

        if self._index is None or not self._entries:
            return []

        query_tokens = tokenize_for_bm25(query)
        scores: np.ndarray = self._index.get_scores(query_tokens)

        # Sort (original_index, score) pairs by score descending
        sorted_pairs = sorted(
            enumerate(scores.tolist()),
            key=lambda pair: pair[1],
            reverse=True,
        )

        results: list[SparseResult] = []
        rank = 1
        for idx, score in sorted_pairs:
            if len(results) >= top_k:
                break

            entry = self._entries[idx]
            if not self._matches_filters(entry, filters):
                continue

            results.append(
                SparseResult(
                    chunk_id=entry.chunk_id,
                    document_id=entry.document_id,
                    content=entry.content_raw,
                    section=entry.section,
                    section_title=entry.section_title,
                    bm25_score=score,
                    rank=rank,
                    metadata=entry.metadata,
                )
            )
            rank += 1

        return results

    def get_stats(self) -> dict[str, Any]:
        """Return runtime statistics about the current index state.

        Returns:
            Dictionary with keys:

            - ``is_built`` (bool): whether the index has been built.
            - ``chunk_count`` (int): total number of indexed chunks.
            - ``document_count`` (int): number of unique documents indexed.
        """
        return {
            "is_built": self._is_built,
            "chunk_count": len(self._entries),
            "document_count": self._document_count,
        }

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _matches_filters(entry: _ChunkEntry, filters: SearchFilters) -> bool:
        """Return True if *entry* satisfies every active filter criterion.

        Args:
            entry: In-memory chunk entry to test.
            filters: Caller-supplied filter object (unset fields are ignored).

        Returns:
            ``True`` if the entry passes all active filters, ``False``
            otherwise.
        """
        if filters.document_id is not None and entry.document_id != filters.document_id:
            return False

        if filters.sections is not None and entry.section not in filters.sections:
            return False

        if filters.fiscal_year is not None and entry.fiscal_year != filters.fiscal_year:
            return False

        if filters.company is not None:
            company_lower = filters.company.lower()
            if (
                company_lower not in entry.company_name.lower()
                and company_lower not in entry.ticker.lower()
            ):
                return False

        return True
