"""
HyDE (Hypothetical Document Embeddings) Service

Expands analytical queries by generating a hypothetical 10-K passage via Ollama,
then embedding that document instead of the original query. Falls back gracefully
to direct query embedding when Ollama is unavailable or slow, or when the query
is factual rather than analytical.
"""

from __future__ import annotations

import logging
import re

import httpx

from src.core.config import settings
from src.services.embedding import EmbeddingService

logger = logging.getLogger(__name__)

HYDE_PROMPT_TEMPLATE = """You are a financial analyst reviewing SEC 10-K filings.
Write a detailed paragraph that would appear in an annual report and directly
answer the following question. Use specific financial terminology, metrics, and
the style of formal corporate disclosure documents.

Question: {query}

Hypothetical passage from a 10-K filing:"""

ANALYTICAL_KEYWORDS = {
    "compare",
    "trend",
    "change",
    "evolution",
    "increase",
    "decrease",
    "risk",
    "strategy",
    "outlook",
    "why",
    "how",
    "impact",
    "affect",
    "versus",
    "vs",
    "difference",
    "growth",
    "decline",
    "forecast",
    # Additional analytical patterns common in financial queries
    "drivers",
    "driver",
    "factors",
    "factor",
    "sources",
    "source",
    "causes",
    "cause",
    "reasons",
    "reason",
    "breakdown",
    "contribution",
    "explain",
    "describe",
    "analysis",
    "performance",
    "segment",
}


def is_analytical_query(query: str) -> bool:
    """Return True if the query is likely to benefit from HyDE expansion.

    A query is considered analytical when it contains at least one token from
    ANALYTICAL_KEYWORDS, indicating it asks for comparison, trend analysis, or
    causal reasoning rather than a simple factual lookup.

    Uses regex tokenisation to strip punctuation before matching, so trailing
    characters like ``?`` or ``'s`` don't prevent keyword detection.

    Args:
        query: The raw user query string.

    Returns:
        True if the query is analytical, False if it appears factual.
    """
    tokens = set(re.findall(r"\b[a-z0-9][a-z0-9-]*\b", query.lower()))
    return bool(tokens & ANALYTICAL_KEYWORDS)


class HyDEService:
    """Optionally expands queries using Hypothetical Document Embeddings.

    For analytical queries, generates a hypothetical 10-K passage via Ollama
    and embeds it instead of the raw query, improving dense retrieval recall.
    Falls back silently to direct query embedding on any Ollama failure.

    Args:
        embedding_service: EmbeddingService instance for generating vectors.
        ollama_base_url: Base URL for the Ollama API.
            Defaults to settings.OLLAMA_BASE_URL.
        ollama_model: Model name to use for generation.
            Defaults to settings.OLLAMA_MODEL.
        client: Optional pre-configured AsyncClient (used for testing).
            If None, a new client is created with the default timeout.
    """

    _DEFAULT_TIMEOUT = httpx.Timeout(connect=3.0, read=10.0, write=5.0, pool=2.0)

    def __init__(
        self,
        embedding_service: EmbeddingService,
        ollama_base_url: str | None = None,
        ollama_model: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._embedding_service = embedding_service
        self._base_url = (ollama_base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self._model = ollama_model or settings.OLLAMA_MODEL
        self._client = client or httpx.AsyncClient(timeout=self._DEFAULT_TIMEOUT)

    async def is_available(self) -> bool:
        """Check whether the Ollama API is reachable.

        Performs a lightweight GET /api/tags with a 3-second connect timeout.

        Returns:
            True if Ollama responds with a 2xx status, False otherwise.
        """
        try:
            response = await self._client.get(
                f"{self._base_url}/api/tags",
                timeout=httpx.Timeout(connect=3.0, read=3.0, write=1.0, pool=1.0),
            )
            return response.is_success
        except (httpx.TimeoutException, httpx.ConnectError, httpx.HTTPError):
            return False

    async def generate_hypothetical_doc(self, query: str) -> str:
        """Generate a hypothetical 10-K passage that answers the query.

        Sends the formatted HyDE prompt to Ollama and returns the generated text.

        Args:
            query: The user query to expand into a hypothetical document.

        Returns:
            The generated hypothetical document text as a string.

        Raises:
            httpx.TimeoutException: If Ollama does not respond within timeout.
            httpx.ConnectError: If the Ollama server is unreachable.
            httpx.HTTPStatusError: If Ollama returns a non-2xx response.
        """
        prompt = HYDE_PROMPT_TEMPLATE.format(query=query)
        response = await self._client.post(
            f"{self._base_url}/api/generate",
            json={"model": self._model, "prompt": prompt, "stream": False},
        )
        response.raise_for_status()
        data = response.json()
        return str(data["response"])

    async def expand_query_to_embedding(self, query: str) -> list[float]:
        """Return the embedding vector to use for retrieval, with optional HyDE.

        Decision logic:
        1. If the query is not analytical, embed it directly and skip HyDE
           (logged at DEBUG level).
        2. If HyDE generation fails for any reason (timeout, connection error,
           HTTP error), embed the original query and log a WARNING. Exceptions
           from Ollama are never propagated to the caller.
        3. Otherwise generate a hypothetical document, embed it, and return
           the resulting vector.

        Args:
            query: The raw user query string.

        Returns:
            A single embedding vector as a list of floats.
        """
        if not is_analytical_query(query):
            logger.debug("HyDE skipped: factual query detected — embedding query directly")
            return self._embedding_service.embed_texts([query])[0]

        try:
            hypothetical_doc = await self.generate_hypothetical_doc(query)
            embedding = self._embedding_service.embed_texts([hypothetical_doc])[0]
            logger.debug("HyDE applied: embedded hypothetical document for analytical query")
            return embedding
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logger.warning(
                "Ollama unavailable (%s: %s), skipping HyDE — embedding query directly",
                type(exc).__name__,
                exc,
            )
            return self._embedding_service.embed_texts([query])[0]
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Ollama returned HTTP %d, skipping HyDE — embedding query directly",
                exc.response.status_code,
            )
            return self._embedding_service.embed_texts([query])[0]

    async def aclose(self) -> None:
        """Close the underlying httpx client and release resources."""
        await self._client.aclose()
