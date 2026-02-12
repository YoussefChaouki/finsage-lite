"""
Chunking Schemas

Pydantic schemas for section-aware chunking output.
"""

from pydantic import BaseModel, Field

from src.models.chunk import ContentType, SectionType


class ChunkData(BaseModel):
    """Output of the chunking process for a single chunk.

    Attributes:
        section: SEC 10-K section type (ITEM_1, ITEM_1A, etc.).
        section_title: Human-readable section title (e.g. "Risk Factors").
        content_type: TEXT or TABLE.
        content_raw: Plain text for BM25 (no prefix).
        content_context: Prefixed text for embedding
            ("[Company | 10-K FYxxxx | Section]\\n\\n{text}").
        chunk_index: Sequential index within the section.
        metadata: JSONB-compatible metadata dict.
    """

    section: SectionType
    section_title: str
    content_type: ContentType = ContentType.TEXT
    content_raw: str
    content_context: str
    chunk_index: int
    metadata: dict[str, object] = Field(default_factory=dict)
