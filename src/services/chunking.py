"""
Section-Aware Chunking

Splits parsed 10-K sections into overlapping text chunks with dual content
versions (raw for BM25, prefixed for embedding) and JSONB metadata.
"""

import logging
import math

import tiktoken

from src.core.config import settings
from src.models.chunk import ContentType, SectionType
from src.schemas.chunking import ChunkData

logger = logging.getLogger(__name__)

# Shared encoder — cl100k_base is a good general-purpose tokenizer.
# We don't need the exact MiniLM tokenizer for sizing; approximate counts suffice.
_ENCODER = tiktoken.get_encoding("cl100k_base")


class SectionChunker:
    """Splits section text into overlapping chunks with contextual metadata.

    Each chunk produces two content versions:
        - content_raw: plain text (for BM25, no prefix noise)
        - content_context: "[Company | 10-K FYxxxx | Section]\\n\\n{text}" (for embedding)

    Args:
        chunk_size: Target chunk size in tokens. Defaults to settings.CHUNK_SIZE.
        chunk_overlap: Overlap between consecutive chunks in tokens.
            Defaults to settings.CHUNK_OVERLAP.
    """

    def __init__(
        self,
        chunk_size: int | None = None,
        chunk_overlap: int | None = None,
    ) -> None:
        self._chunk_size = chunk_size if chunk_size is not None else settings.CHUNK_SIZE
        self._chunk_overlap = (
            chunk_overlap if chunk_overlap is not None else settings.CHUNK_OVERLAP
        )

        if self._chunk_overlap >= self._chunk_size:
            raise ValueError(
                f"chunk_overlap ({self._chunk_overlap}) must be less than "
                f"chunk_size ({self._chunk_size})"
            )

    @property
    def chunk_size(self) -> int:
        """Target chunk size in tokens."""
        return self._chunk_size

    @property
    def chunk_overlap(self) -> int:
        """Overlap between consecutive chunks in tokens."""
        return self._chunk_overlap

    def chunk_section(
        self,
        text: str,
        section: SectionType,
        section_title: str,
        company_name: str,
        cik: str,
        fiscal_year: int,
    ) -> list[ChunkData]:
        """Split section text into overlapping chunks with metadata.

        Args:
            text: Cleaned plain text of the section (from parser text_content).
            section: SectionType enum value.
            section_title: Human-readable title (e.g. "Risk Factors").
            company_name: Company name for context prefix.
            cik: Central Index Key.
            fiscal_year: Fiscal year (e.g. 2024).

        Returns:
            List of ChunkData objects, one per chunk. Empty list if text is blank.
        """
        text = text.strip()
        if not text:
            logger.warning("Empty text for %s — skipping", section.value)
            return []

        raw_chunks = self._split_tokens(text)

        if not raw_chunks:
            return []

        total_chunks = len(raw_chunks)
        prefix = self._build_prefix(company_name, fiscal_year, section_title)

        chunks: list[ChunkData] = []
        for idx, raw_text in enumerate(raw_chunks):
            content_context = f"{prefix}\n\n{raw_text}"

            metadata: dict[str, object] = {
                "company": company_name,
                "cik": cik,
                "fiscal_year": fiscal_year,
                "section": section.value,
                "section_title": section_title,
                "chunk_index": idx,
                "total_chunks": total_chunks,
                "page_approx": self._estimate_page(idx, total_chunks),
            }

            chunks.append(
                ChunkData(
                    section=section,
                    section_title=section_title,
                    content_type=ContentType.TEXT,
                    content_raw=raw_text,
                    content_context=content_context,
                    chunk_index=idx,
                    metadata=metadata,
                )
            )

        logger.info(
            "Chunked %s into %d chunks (~%d tokens each, %d overlap)",
            section.value,
            total_chunks,
            self._chunk_size,
            self._chunk_overlap,
        )
        return chunks

    def _split_tokens(self, text: str) -> list[str]:
        """Split text into overlapping chunks based on token boundaries.

        Encodes text to tokens, slices into windows of chunk_size with
        chunk_overlap stride, then decodes back to text.

        Args:
            text: Plain text to split.

        Returns:
            List of text strings, each approximately chunk_size tokens.
        """
        tokens = _ENCODER.encode(text)
        total_tokens = len(tokens)

        if total_tokens <= self._chunk_size:
            return [text]

        step = self._chunk_size - self._chunk_overlap
        chunks: list[str] = []

        for start in range(0, total_tokens, step):
            end = min(start + self._chunk_size, total_tokens)
            chunk_text = _ENCODER.decode(tokens[start:end])
            chunks.append(chunk_text.strip())

            # Stop if we've reached the end
            if end >= total_tokens:
                break

        return chunks

    @staticmethod
    def _build_prefix(company_name: str, fiscal_year: int, section_title: str) -> str:
        """Build the contextual prefix for embedding.

        Format: "[Company | 10-K FYxxxx | Section Title]"

        Args:
            company_name: Company name.
            fiscal_year: Fiscal year.
            section_title: Section title.

        Returns:
            Formatted prefix string.
        """
        return f"[{company_name} | 10-K FY{fiscal_year} | {section_title}]"

    @staticmethod
    def _estimate_page(chunk_index: int, total_chunks: int) -> int:
        """Estimate the approximate page number for a chunk.

        Uses a simple proportional estimate assuming ~4 chunks per page
        (a typical 10-K page has ~1000 tokens).

        Args:
            chunk_index: Zero-based index of the chunk.
            total_chunks: Total number of chunks in the section.

        Returns:
            Estimated 1-based page number.
        """
        chunks_per_page = 4
        total_pages = max(1, math.ceil(total_chunks / chunks_per_page))
        page = math.ceil((chunk_index + 1) / chunks_per_page)
        return min(page, total_pages)

    @staticmethod
    def count_tokens(text: str) -> int:
        """Count the number of tokens in text using the shared encoder.

        Args:
            text: Text to count tokens for.

        Returns:
            Token count.
        """
        return len(_ENCODER.encode(text))
