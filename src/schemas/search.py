"""
Search Schemas

Pydantic v2 request/response schemas for the search layer.
Covers dense retrieval (DenseResult), sparse BM25 retrieval (SparseResult),
hybrid results (SearchResult), and API request/response types.
"""

from __future__ import annotations

import uuid
from typing import Any, Literal

from pydantic import BaseModel, Field

from src.models.chunk import SectionType


class SearchFilters(BaseModel):
    """Criteria for pre-filtering chunks before vector similarity search.

    All fields are optional. Unset fields are ignored (no filtering applied).

    Attributes:
        document_id: Restrict search to a single document.
        sections: Restrict search to one or more SEC 10-K sections.
        fiscal_year: Restrict search to documents filed in a specific fiscal year.
        company: Case-insensitive substring match against company name or ticker.
    """

    document_id: uuid.UUID | None = None
    sections: list[SectionType] | None = None
    fiscal_year: int | None = Field(default=None, ge=1993)
    company: str | None = None


class DenseResult(BaseModel):
    """A single result from dense (embedding-based) retrieval.

    Attributes:
        chunk_id: Unique identifier of the chunk.
        document_id: Parent document UUID.
        content: Raw text content of the chunk (human-readable).
        section: SEC 10-K section this chunk belongs to.
        section_title: Human-readable section title.
        score: Cosine similarity score in [0, 1]; higher is more relevant.
        metadata: Additional metadata dict (page_approx, table_title, etc.).
    """

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    section: SectionType
    section_title: str
    score: float
    metadata: dict[str, Any]


class SparseResult(BaseModel):
    """A single result from sparse (BM25) retrieval.

    Attributes:
        chunk_id: Unique identifier of the chunk.
        document_id: Parent document UUID.
        content: Raw text content of the chunk (human-readable).
        section: SEC 10-K section this chunk belongs to.
        section_title: Human-readable section title.
        bm25_score: Raw BM25 score; higher means more lexically relevant.
        rank: 1-based rank within the result list (1 = best).
        metadata: Additional metadata dict (page_approx, table_title, etc.).
    """

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    section: SectionType
    section_title: str
    bm25_score: float
    rank: int
    metadata: dict[str, Any]


class SearchResult(BaseModel):
    """A single result from hybrid (RRF-fused) retrieval.

    Attributes:
        chunk_id: Unique identifier of the chunk.
        document_id: Parent document UUID.
        content: Raw text content of the chunk (human-readable).
        section: SEC 10-K section this chunk belongs to.
        section_title: Human-readable section title.
        score: RRF-normalised score in [0, 1]; higher is more relevant.
        dense_score: Original cosine similarity score (debug/comparison).
        sparse_score: Original BM25 score (debug/comparison).
        metadata: Additional metadata dict (page_approx, table_title, etc.).
    """

    chunk_id: uuid.UUID
    document_id: uuid.UUID
    content: str
    section: SectionType
    section_title: str
    score: float
    dense_score: float | None = None
    sparse_score: float | None = None
    metadata: dict[str, Any]


class SearchRequest(BaseModel):
    """Request body for POST /api/v1/search.

    Attributes:
        query: Natural language question or keyword query.
        top_k: Number of results to return (1–20).
        search_mode: Retrieval strategy to use.
        use_hyde: Whether to attempt HyDE query expansion before dense search.
        filters: Optional pre-filtering criteria applied before retrieval.
    """

    query: str
    top_k: int = Field(default=5, ge=1, le=20)
    search_mode: Literal["dense", "sparse", "hybrid"] = "hybrid"
    use_hyde: bool = False
    filters: SearchFilters = Field(default_factory=SearchFilters)


class SearchResponse(BaseModel):
    """Response body for POST /api/v1/search.

    Attributes:
        answer: LLM-generated answer (null until Sprint 3 generation layer).
        results: Ordered list of matching chunks (best first).
        total: Number of results returned.
        query: Echo of the original query string.
        search_mode: Echo of the search mode used.
        hyde_used: True if HyDE expansion was actually applied.
        latency_ms: End-to-end retrieval latency in milliseconds.
    """

    answer: str | None = None
    results: list[SearchResult]
    total: int
    query: str
    search_mode: str
    hyde_used: bool
    latency_ms: float


class SearchHealthResponse(BaseModel):
    """Response body for GET /api/v1/search/health.

    Attributes:
        bm25_index_size: Number of chunks currently in the BM25 index.
        bm25_is_built: True if the BM25 index has been built.
        hyde_available: True if the Ollama server is reachable.
        ollama_model: Name of the configured Ollama model.
    """

    bm25_index_size: int
    bm25_is_built: bool
    hyde_available: bool
    ollama_model: str
