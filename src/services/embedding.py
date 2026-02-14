"""
Embedding Service

Generates embeddings using sentence-transformers (all-MiniLM-L6-v2) and stores
them in pgvector via the chunk repository. Supports batch processing for efficiency.
"""

import logging
import uuid

from sentence_transformers import SentenceTransformer
from sqlalchemy.ext.asyncio import AsyncSession

from src.core.config import settings
from src.models.chunk import Chunk
from src.repositories.chunk import ChunkRepository
from src.schemas.chunking import ChunkData

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Generates embeddings and stores chunks with vectors in pgvector.

    Loads the sentence-transformers model once at init time and reuses it
    for all subsequent calls. Batch processing is used to avoid OOM on
    large documents.

    Args:
        model_name: HuggingFace model identifier.
            Defaults to settings.EMBEDDING_MODEL.
        batch_size: Number of texts to encode per batch.
            Defaults to settings.EMBEDDING_BATCH_SIZE.
    """

    def __init__(
        self,
        model_name: str | None = None,
        batch_size: int | None = None,
    ) -> None:
        self._model_name = model_name or settings.EMBEDDING_MODEL
        self._batch_size = batch_size or settings.EMBEDDING_BATCH_SIZE
        self._model = SentenceTransformer(self._model_name)
        self._dimension = settings.EMBEDDING_DIMENSION

        logger.info(
            "EmbeddingService initialized: model=%s, dimension=%d, batch_size=%d",
            self._model_name,
            self._dimension,
            self._batch_size,
        )

    @property
    def model_name(self) -> str:
        """Name of the loaded embedding model."""
        return self._model_name

    @property
    def dimension(self) -> int:
        """Dimension of the output embeddings."""
        return self._dimension

    @property
    def batch_size(self) -> int:
        """Number of texts encoded per batch."""
        return self._batch_size

    def embed_texts(self, texts: list[str]) -> list[list[float]]:
        """Generate embeddings for a list of texts.

        Processes in batches of batch_size for memory efficiency.
        Uses content as-is — callers should pass content_context (prefixed)
        for semantic search or content_raw for BM25-aligned embeddings.

        Args:
            texts: List of text strings to embed.

        Returns:
            List of embedding vectors, each of length self.dimension.

        Raises:
            ValueError: If texts is empty.
        """
        if not texts:
            raise ValueError("Cannot embed an empty list of texts")

        logger.debug("Embedding %d texts in batches of %d", len(texts), self._batch_size)

        all_embeddings: list[list[float]] = []

        for i in range(0, len(texts), self._batch_size):
            batch = texts[i : i + self._batch_size]
            batch_embeddings = self._model.encode(
                batch,
                show_progress_bar=False,
                normalize_embeddings=True,
            )
            all_embeddings.extend(batch_embeddings.tolist())

        logger.info("Generated %d embeddings (dim=%d)", len(all_embeddings), self._dimension)
        return all_embeddings

    async def embed_and_store(
        self,
        chunks: list[ChunkData],
        document_id: uuid.UUID,
        session: AsyncSession,
    ) -> list[Chunk]:
        """Embed chunks and persist them with vectors to the database.

        1. Extracts content_context from each ChunkData (prefixed text for embedding).
        2. Generates embeddings in batches.
        3. Creates Chunk ORM instances with the embeddings.
        4. Bulk-inserts via ChunkRepository.

        Args:
            chunks: List of ChunkData from the chunking service.
            document_id: UUID of the parent document.
            session: Async DB session for the transaction.

        Returns:
            List of persisted Chunk ORM instances.

        Raises:
            ValueError: If chunks is empty.
        """
        if not chunks:
            raise ValueError("Cannot embed and store an empty list of chunks")

        # 1. Extract texts for embedding (use content_context = prefixed version)
        texts = [chunk.content_context for chunk in chunks]

        # 2. Generate embeddings
        embeddings = self.embed_texts(texts)

        # 3. Build Chunk ORM objects
        chunk_models: list[Chunk] = []
        for chunk_data, embedding in zip(chunks, embeddings, strict=True):
            chunk_model = Chunk(
                document_id=document_id,
                section=chunk_data.section,
                section_title=chunk_data.section_title,
                content_type=chunk_data.content_type,
                content_raw=chunk_data.content_raw,
                content_context=chunk_data.content_context,
                embedding=embedding,
                chunk_index=chunk_data.chunk_index,
                metadata_=chunk_data.metadata,
            )
            chunk_models.append(chunk_model)

        # 4. Persist via repository
        repo = ChunkRepository(session)
        await repo.create_many(chunk_models)

        logger.info(
            "Embedded and stored %d chunks for document %s",
            len(chunk_models),
            document_id,
        )
        return chunk_models
