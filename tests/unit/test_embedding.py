"""
Unit tests for EmbeddingService.

Tests embedding dimension, batch processing, normalization,
and basic similarity properties without requiring a database.
"""

import numpy as np
import pytest

from src.models.chunk import ContentType, SectionType
from src.schemas.chunking import ChunkData
from src.services.embedding import EmbeddingService


@pytest.fixture(scope="module")
def embedding_service() -> EmbeddingService:
    """Module-scoped EmbeddingService (model loads once for all tests)."""
    return EmbeddingService(batch_size=8)


# --- Dimension ---


def test_embed_texts_returns_384_dimensions(embedding_service: EmbeddingService) -> None:
    """Each embedding vector has exactly 384 dimensions (MiniLM-L6-v2)."""
    embeddings = embedding_service.embed_texts(["Revenue grew 15% year-over-year."])
    assert len(embeddings) == 1
    assert len(embeddings[0]) == 384


def test_dimension_property(embedding_service: EmbeddingService) -> None:
    """The dimension property matches the expected value."""
    assert embedding_service.dimension == 384


# --- Batch processing ---


def test_embed_texts_multiple_inputs(embedding_service: EmbeddingService) -> None:
    """Multiple texts produce the same number of embeddings."""
    texts = [
        "Apple Inc. reported revenue of $394 billion.",
        "Risk factors include supply chain disruptions.",
        "The company operates in multiple segments worldwide.",
    ]
    embeddings = embedding_service.embed_texts(texts)
    assert len(embeddings) == 3
    for emb in embeddings:
        assert len(emb) == 384


def test_embed_texts_batch_processing(embedding_service: EmbeddingService) -> None:
    """Large input is correctly processed in batches (batch_size=8)."""
    texts = [f"Text number {i} about financial performance." for i in range(25)]
    embeddings = embedding_service.embed_texts(texts)
    assert len(embeddings) == 25
    for emb in embeddings:
        assert len(emb) == 384


def test_embed_texts_single_batch(embedding_service: EmbeddingService) -> None:
    """Input smaller than batch_size works without error."""
    texts = ["Short text."]
    embeddings = embedding_service.embed_texts(texts)
    assert len(embeddings) == 1


# --- Normalization ---


def test_embeddings_are_normalized(embedding_service: EmbeddingService) -> None:
    """Embeddings should be L2-normalized (unit length)."""
    embeddings = embedding_service.embed_texts(
        [
            "Operating income was $120 million in fiscal year 2024.",
            "Material risks include regulatory changes and market volatility.",
        ]
    )
    for emb in embeddings:
        norm = np.linalg.norm(emb)
        assert abs(norm - 1.0) < 1e-4, f"Embedding norm is {norm}, expected ~1.0"


# --- Cosine similarity ---


def test_similar_texts_have_higher_similarity(embedding_service: EmbeddingService) -> None:
    """Semantically similar texts should have higher cosine similarity."""
    texts = [
        "Apple reported record revenue growth in Q4.",  # A: revenue topic
        "The company saw strong revenue increase last quarter.",  # B: similar to A
        "The weather forecast predicts rain tomorrow.",  # C: unrelated
    ]
    embeddings = embedding_service.embed_texts(texts)

    def cosine_sim(a: list[float], b: list[float]) -> float:
        va = np.array(a)
        vb = np.array(b)
        return float(np.dot(va, vb) / (np.linalg.norm(va) * np.linalg.norm(vb)))

    sim_ab = cosine_sim(embeddings[0], embeddings[1])
    sim_ac = cosine_sim(embeddings[0], embeddings[2])

    assert sim_ab > sim_ac, (
        f"Similar texts should have higher similarity: "
        f"sim(A,B)={sim_ab:.3f} should be > sim(A,C)={sim_ac:.3f}"
    )


# --- Determinism ---


def test_same_text_produces_same_embedding(embedding_service: EmbeddingService) -> None:
    """Identical texts produce identical embeddings."""
    text = "The company's total assets were $350 billion."
    emb1 = embedding_service.embed_texts([text])
    emb2 = embedding_service.embed_texts([text])
    np.testing.assert_allclose(emb1[0], emb2[0], atol=1e-6)


# --- Edge cases ---


def test_embed_texts_empty_raises_error(embedding_service: EmbeddingService) -> None:
    """Empty input list raises ValueError."""
    with pytest.raises(ValueError, match="empty"):
        embedding_service.embed_texts([])


def test_embed_texts_long_text_truncated(embedding_service: EmbeddingService) -> None:
    """Very long text is handled without error (model truncates internally)."""
    long_text = "financial performance analysis " * 500  # way beyond 256 tokens
    embeddings = embedding_service.embed_texts([long_text])
    assert len(embeddings) == 1
    assert len(embeddings[0]) == 384


# --- ChunkData compatibility ---


def test_embed_chunk_data_content_context(embedding_service: EmbeddingService) -> None:
    """content_context from ChunkData produces valid embeddings."""
    chunk = ChunkData(
        section=SectionType.ITEM_7,
        section_title="MD&A",
        content_type=ContentType.TEXT,
        content_raw="Revenue grew 15% driven by strong iPhone sales.",
        content_context=(
            "[Apple Inc. | 10-K FY2024 | MD&A]\n\nRevenue grew 15% driven by strong iPhone sales."
        ),
        chunk_index=0,
        metadata={"company": "Apple Inc.", "fiscal_year": 2024},
    )
    embeddings = embedding_service.embed_texts([chunk.content_context])
    assert len(embeddings) == 1
    assert len(embeddings[0]) == 384


# --- Model name ---


def test_model_name_property(embedding_service: EmbeddingService) -> None:
    """model_name property returns the configured model."""
    assert embedding_service.model_name == "all-MiniLM-L6-v2"


# --- Float type ---


def test_embeddings_are_float_lists(embedding_service: EmbeddingService) -> None:
    """Embeddings are returned as list[list[float]]."""
    embeddings = embedding_service.embed_texts(["test"])
    assert isinstance(embeddings, list)
    assert isinstance(embeddings[0], list)
    assert isinstance(embeddings[0][0], float)
