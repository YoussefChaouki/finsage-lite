"""
Unit tests for Section-Aware Chunking.

Tests chunk size, overlap, metadata correctness, prefix formatting,
and edge cases (empty text, single-chunk text, exact boundary).
"""

import json

import pytest

from src.models.chunk import ContentType, SectionType
from src.schemas.table import StructuredTable
from src.services.chunking import SectionChunker


@pytest.fixture()
def chunker() -> SectionChunker:
    """SectionChunker with default settings (220 tokens, 50 overlap)."""
    return SectionChunker(chunk_size=220, chunk_overlap=50)


def _generate_text(target_tokens: int) -> str:
    """Generate repeating text of approximately target_tokens tokens.

    Uses simple words that tokenize predictably (1 word ≈ 1 token).
    """
    words = ["revenue", "growth", "risk", "market", "operating", "income", "fiscal", "year"]
    repeated = (words * ((target_tokens // len(words)) + 1))[:target_tokens]
    return " ".join(repeated)


# --- Basic chunking ---


def test_chunk_1000_tokens_produces_about_6_chunks(chunker: SectionChunker) -> None:
    """A text of ~1000 tokens should produce ~6 chunks with 220 size and 50 overlap."""
    text = _generate_text(1000)
    chunks = chunker.chunk_section(
        text=text,
        section=SectionType.ITEM_7,
        section_title="MD&A",
        company_name="Test Corp",
        cik="0001234567",
        fiscal_year=2024,
    )
    # With step=170 (220-50), 1000 tokens → ceil(1000/170) ≈ 6 chunks
    assert 5 <= len(chunks) <= 7


def test_chunk_size_within_bounds(chunker: SectionChunker) -> None:
    """Each chunk should have at most chunk_size tokens."""
    text = _generate_text(1000)
    chunks = chunker.chunk_section(
        text=text,
        section=SectionType.ITEM_1,
        section_title="Business",
        company_name="Test Corp",
        cik="0001234567",
        fiscal_year=2024,
    )
    for chunk in chunks:
        token_count = SectionChunker.count_tokens(chunk.content_raw)
        assert token_count <= chunker.chunk_size + 5, (
            f"Chunk {chunk.chunk_index} has {token_count} tokens (max {chunker.chunk_size})"
        )


def test_chunks_have_overlap(chunker: SectionChunker) -> None:
    """Consecutive chunks should share overlapping text."""
    text = _generate_text(600)
    chunks = chunker.chunk_section(
        text=text,
        section=SectionType.ITEM_1A,
        section_title="Risk Factors",
        company_name="Test Corp",
        cik="0001234567",
        fiscal_year=2024,
    )
    assert len(chunks) >= 2
    # Check that consecutive chunks share some text
    for i in range(len(chunks) - 1):
        current_words = set(chunks[i].content_raw.split()[-30:])
        next_words = set(chunks[i + 1].content_raw.split()[:30])
        overlap = current_words & next_words
        assert len(overlap) > 0, f"No overlap between chunk {i} and {i + 1}"


# --- Content versions ---


def test_content_raw_is_plain_text(chunker: SectionChunker) -> None:
    """content_raw should not contain the context prefix."""
    text = _generate_text(100)
    chunks = chunker.chunk_section(
        text=text,
        section=SectionType.ITEM_7,
        section_title="MD&A",
        company_name="Acme Inc.",
        cik="0009999999",
        fiscal_year=2023,
    )
    assert len(chunks) == 1
    assert "[Acme Inc." not in chunks[0].content_raw
    assert "10-K FY2023" not in chunks[0].content_raw


def test_content_context_has_prefix(chunker: SectionChunker) -> None:
    """content_context should start with the formatted prefix."""
    text = _generate_text(100)
    chunks = chunker.chunk_section(
        text=text,
        section=SectionType.ITEM_7,
        section_title="MD&A",
        company_name="Acme Inc.",
        cik="0009999999",
        fiscal_year=2023,
    )
    expected_prefix = "[Acme Inc. | 10-K FY2023 | MD&A]"
    assert chunks[0].content_context.startswith(expected_prefix)
    # Raw text follows after two newlines
    assert f"{expected_prefix}\n\n" in chunks[0].content_context


def test_content_context_contains_raw_text(chunker: SectionChunker) -> None:
    """content_context should contain the same text as content_raw after the prefix."""
    text = _generate_text(100)
    chunks = chunker.chunk_section(
        text=text,
        section=SectionType.ITEM_1,
        section_title="Business",
        company_name="Test Corp",
        cik="0001234567",
        fiscal_year=2024,
    )
    for chunk in chunks:
        assert chunk.content_raw in chunk.content_context


# --- Metadata ---


def test_metadata_fields_present(chunker: SectionChunker) -> None:
    """Each chunk metadata contains all required fields."""
    text = _generate_text(500)
    chunks = chunker.chunk_section(
        text=text,
        section=SectionType.ITEM_1A,
        section_title="Risk Factors",
        company_name="Test Corp",
        cik="0001234567",
        fiscal_year=2024,
    )
    required_keys = {
        "company",
        "cik",
        "fiscal_year",
        "section",
        "section_title",
        "chunk_index",
        "total_chunks",
        "page_approx",
    }
    for chunk in chunks:
        assert required_keys.issubset(chunk.metadata.keys()), (
            f"Missing keys: {required_keys - chunk.metadata.keys()}"
        )


def test_metadata_values_correct(chunker: SectionChunker) -> None:
    """Metadata values match the input parameters."""
    text = _generate_text(500)
    chunks = chunker.chunk_section(
        text=text,
        section=SectionType.ITEM_8,
        section_title="Financial Statements",
        company_name="Test Corp",
        cik="0001234567",
        fiscal_year=2024,
    )
    total = len(chunks)
    for i, chunk in enumerate(chunks):
        assert chunk.metadata["company"] == "Test Corp"
        assert chunk.metadata["cik"] == "0001234567"
        assert chunk.metadata["fiscal_year"] == 2024
        assert chunk.metadata["section"] == "ITEM_8"
        assert chunk.metadata["section_title"] == "Financial Statements"
        assert chunk.metadata["chunk_index"] == i
        assert chunk.metadata["total_chunks"] == total


def test_chunk_index_sequential(chunker: SectionChunker) -> None:
    """chunk_index values are sequential starting from 0."""
    text = _generate_text(800)
    chunks = chunker.chunk_section(
        text=text,
        section=SectionType.ITEM_7,
        section_title="MD&A",
        company_name="Test Corp",
        cik="0001234567",
        fiscal_year=2024,
    )
    indices = [c.chunk_index for c in chunks]
    assert indices == list(range(len(chunks)))


def test_content_type_is_text(chunker: SectionChunker) -> None:
    """All chunks from chunk_section should have TEXT content type."""
    text = _generate_text(300)
    chunks = chunker.chunk_section(
        text=text,
        section=SectionType.ITEM_1,
        section_title="Business",
        company_name="Test Corp",
        cik="0001234567",
        fiscal_year=2024,
    )
    for chunk in chunks:
        assert chunk.content_type == ContentType.TEXT


# --- Edge cases ---


def test_empty_text_returns_empty_list(chunker: SectionChunker) -> None:
    """Empty or whitespace-only text produces no chunks."""
    for text in ["", "   ", "\n\n"]:
        chunks = chunker.chunk_section(
            text=text,
            section=SectionType.ITEM_1,
            section_title="Business",
            company_name="Test Corp",
            cik="0001234567",
            fiscal_year=2024,
        )
        assert chunks == []


def test_short_text_single_chunk(chunker: SectionChunker) -> None:
    """Text shorter than chunk_size produces exactly one chunk."""
    text = "This is a short text about company revenue growth."
    chunks = chunker.chunk_section(
        text=text,
        section=SectionType.ITEM_1,
        section_title="Business",
        company_name="Test Corp",
        cik="0001234567",
        fiscal_year=2024,
    )
    assert len(chunks) == 1
    assert chunks[0].content_raw == text
    assert chunks[0].chunk_index == 0
    assert chunks[0].metadata["total_chunks"] == 1


def test_exact_chunk_size_single_chunk() -> None:
    """Text at or below chunk_size tokens produces one chunk."""
    chunker = SectionChunker(chunk_size=50, chunk_overlap=10)
    # Build text that is exactly 50 tokens by encoding/decoding
    base_text = _generate_text(55)
    import tiktoken

    enc = tiktoken.get_encoding("cl100k_base")
    tokens = enc.encode(base_text)[:50]
    text = enc.decode(tokens)
    assert SectionChunker.count_tokens(text) == 50

    chunks = chunker.chunk_section(
        text=text,
        section=SectionType.ITEM_7A,
        section_title="Market Risk",
        company_name="Test Corp",
        cik="0001234567",
        fiscal_year=2024,
    )
    assert len(chunks) == 1


# --- Configurable parameters ---


def test_custom_chunk_size() -> None:
    """Custom chunk_size is respected."""
    chunker = SectionChunker(chunk_size=100, chunk_overlap=20)
    text = _generate_text(500)
    chunks = chunker.chunk_section(
        text=text,
        section=SectionType.ITEM_1,
        section_title="Business",
        company_name="Test Corp",
        cik="0001234567",
        fiscal_year=2024,
    )
    # step = 80, so ~7 chunks
    assert len(chunks) >= 5
    for chunk in chunks:
        token_count = SectionChunker.count_tokens(chunk.content_raw)
        assert token_count <= 105  # small tolerance for token boundary


def test_overlap_greater_than_size_raises_error() -> None:
    """Overlap >= chunk_size raises ValueError."""
    with pytest.raises(ValueError, match="chunk_overlap.*must be less than"):
        SectionChunker(chunk_size=100, chunk_overlap=100)
    with pytest.raises(ValueError, match="chunk_overlap.*must be less than"):
        SectionChunker(chunk_size=100, chunk_overlap=150)


# --- Token counting ---


def test_count_tokens_basic() -> None:
    """count_tokens returns a reasonable count for known text."""
    count = SectionChunker.count_tokens("hello world")
    assert count == 2


def test_count_tokens_empty() -> None:
    """count_tokens returns 0 for empty string."""
    assert SectionChunker.count_tokens("") == 0


# --- Prefix formatting ---


def test_build_prefix_format() -> None:
    """Prefix follows the expected format."""
    prefix = SectionChunker._build_prefix("Apple Inc.", 2024, "Risk Factors")
    assert prefix == "[Apple Inc. | 10-K FY2024 | Risk Factors]"


# --- Page estimation ---


def test_page_approx_increases_with_chunks(chunker: SectionChunker) -> None:
    """page_approx should increase as chunk_index grows."""
    text = _generate_text(2000)
    chunks = chunker.chunk_section(
        text=text,
        section=SectionType.ITEM_7,
        section_title="MD&A",
        company_name="Test Corp",
        cik="0001234567",
        fiscal_year=2024,
    )
    pages = [c.metadata["page_approx"] for c in chunks]
    # Pages should be non-decreasing
    assert pages == sorted(pages)
    # First page is 1
    assert pages[0] == 1


# --- Section field correctness ---


def test_section_field_matches_input(chunker: SectionChunker) -> None:
    """chunk.section matches the input SectionType."""
    text = _generate_text(300)
    for section_type in [SectionType.ITEM_1, SectionType.ITEM_1A, SectionType.ITEM_8]:
        chunks = chunker.chunk_section(
            text=text,
            section=section_type,
            section_title="Test",
            company_name="Test Corp",
            cik="0001234567",
            fiscal_year=2024,
        )
        for chunk in chunks:
            assert chunk.section == section_type


# --- Full text coverage ---


def test_all_text_covered(chunker: SectionChunker) -> None:
    """Concatenated chunks cover the full input text (no gaps)."""
    text = _generate_text(600)
    chunks = chunker.chunk_section(
        text=text,
        section=SectionType.ITEM_1,
        section_title="Business",
        company_name="Test Corp",
        cik="0001234567",
        fiscal_year=2024,
    )
    # Every word in the input should appear in at least one chunk
    input_words = set(text.split())
    covered_words: set[str] = set()
    for chunk in chunks:
        covered_words.update(chunk.content_raw.split())
    missing = input_words - covered_words
    assert not missing, f"Missing words: {missing}"


# ---------------------------------------------------------------------------
# chunk_tables() tests
# ---------------------------------------------------------------------------


def _make_table(title: str = "Revenue Summary", row_count: int = 3) -> StructuredTable:
    """Build a minimal StructuredTable fixture."""
    headers = ["Item", "2024", "2023"]
    rows = [
        {"Item": f"Row {i}", "2024": str(i * 100), "2023": str(i * 90)}
        for i in range(1, row_count + 1)
    ]
    return StructuredTable(
        title=title,
        headers=headers,
        rows=rows,
        row_count=row_count,
        source_section="ITEM_8",
    )


@pytest.fixture()
def two_tables() -> list[StructuredTable]:
    return [_make_table("Revenue Summary"), _make_table("Operating Expenses", row_count=2)]


def test_chunk_tables_empty_returns_empty_list(chunker: SectionChunker) -> None:
    """Empty table list produces no chunks."""
    result = chunker.chunk_tables(
        tables=[],
        section=SectionType.ITEM_8,
        section_title="Financial Statements",
        company_name="Test Corp",
        cik="0001234567",
        fiscal_year=2024,
    )
    assert result == []


def test_chunk_tables_two_tables_two_chunks(
    chunker: SectionChunker, two_tables: list[StructuredTable]
) -> None:
    """Two tables produce exactly two ChunkData objects."""
    chunks = chunker.chunk_tables(
        tables=two_tables,
        section=SectionType.ITEM_8,
        section_title="Financial Statements",
        company_name="Test Corp",
        cik="0001234567",
        fiscal_year=2024,
    )
    assert len(chunks) == 2


def test_chunk_tables_content_type_is_table(
    chunker: SectionChunker, two_tables: list[StructuredTable]
) -> None:
    """All table chunks have ContentType.TABLE."""
    chunks = chunker.chunk_tables(
        tables=two_tables,
        section=SectionType.ITEM_8,
        section_title="Financial Statements",
        company_name="Test Corp",
        cik="0001234567",
        fiscal_year=2024,
    )
    for chunk in chunks:
        assert chunk.content_type == ContentType.TABLE


def test_chunk_tables_content_raw_is_description_not_json(
    chunker: SectionChunker,
) -> None:
    """content_raw is the plain-text description, not raw JSON."""
    table = _make_table("Income Statement")
    chunks = chunker.chunk_tables(
        tables=[table],
        section=SectionType.ITEM_8,
        section_title="Financial Statements",
        company_name="Acme Inc.",
        cik="0009999999",
        fiscal_year=2024,
    )
    assert len(chunks) == 1
    raw = chunks[0].content_raw
    # Should start with the description preamble, not a JSON brace
    assert raw.startswith("Financial table:")
    assert not raw.startswith("{")


def test_chunk_tables_metadata_table_data_parseable_json(
    chunker: SectionChunker,
) -> None:
    """metadata['table_data'] deserialises to a dict with 'headers' and 'rows'."""
    table = _make_table()
    chunks = chunker.chunk_tables(
        tables=[table],
        section=SectionType.ITEM_8,
        section_title="Financial Statements",
        company_name="Test Corp",
        cik="0001234567",
        fiscal_year=2024,
    )
    table_data = json.loads(str(chunks[0].metadata["table_data"]))
    assert "headers" in table_data
    assert "rows" in table_data
    assert isinstance(table_data["rows"], list)


def test_chunk_tables_metadata_table_title_present(chunker: SectionChunker) -> None:
    """metadata['table_title'] matches the StructuredTable title."""
    table = _make_table("Consolidated Balance Sheet")
    chunks = chunker.chunk_tables(
        tables=[table],
        section=SectionType.ITEM_8,
        section_title="Financial Statements",
        company_name="Test Corp",
        cik="0001234567",
        fiscal_year=2024,
    )
    assert chunks[0].metadata["table_title"] == "Consolidated Balance Sheet"


def test_chunk_tables_metadata_table_row_count(chunker: SectionChunker) -> None:
    """metadata['table_row_count'] equals the table's row_count."""
    table = _make_table(row_count=5)
    chunks = chunker.chunk_tables(
        tables=[table],
        section=SectionType.ITEM_8,
        section_title="Financial Statements",
        company_name="Test Corp",
        cik="0001234567",
        fiscal_year=2024,
    )
    assert chunks[0].metadata["table_row_count"] == 5


def test_chunk_tables_content_context_starts_with_prefix(chunker: SectionChunker) -> None:
    """content_context starts with the expected contextual prefix."""
    table = _make_table()
    chunks = chunker.chunk_tables(
        tables=[table],
        section=SectionType.ITEM_8,
        section_title="Financial Statements",
        company_name="Acme Inc.",
        cik="0009999999",
        fiscal_year=2023,
    )
    expected_prefix = "[Acme Inc. | 10-K FY2023 | Financial Statements]"
    assert chunks[0].content_context.startswith(expected_prefix)
    assert f"{expected_prefix}\n\n" in chunks[0].content_context


def test_chunk_tables_chunk_index_offset(chunker: SectionChunker) -> None:
    """chunk_index starts at chunk_index_offset and increments by 1 per table."""
    tables = [_make_table(f"Table {i}") for i in range(3)]
    offset = 7
    chunks = chunker.chunk_tables(
        tables=tables,
        section=SectionType.ITEM_8,
        section_title="Financial Statements",
        company_name="Test Corp",
        cik="0001234567",
        fiscal_year=2024,
        chunk_index_offset=offset,
    )
    assert [c.chunk_index for c in chunks] == [7, 8, 9]


def test_chunk_tables_default_offset_is_zero(chunker: SectionChunker) -> None:
    """With no offset, chunk_index starts at 0."""
    chunks = chunker.chunk_tables(
        tables=[_make_table()],
        section=SectionType.ITEM_8,
        section_title="Financial Statements",
        company_name="Test Corp",
        cik="0001234567",
        fiscal_year=2024,
    )
    assert chunks[0].chunk_index == 0
