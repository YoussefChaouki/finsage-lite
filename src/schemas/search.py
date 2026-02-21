"""
Search Schemas

Pydantic v2 request/response schemas for the dense retrieval layer.
Additional schemas (SearchRequest, SearchResult, SearchResponse) will be
added in Sprint 2 Task 2.5 when the full search endpoint is wired up.
"""

from __future__ import annotations

import uuid
from typing import Any

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
