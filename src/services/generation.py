"""
Generation Service

Produces a cited LLM answer from retrieved chunks using Ollama.
Falls back gracefully to None when Ollama is unavailable or times slow,
so the search endpoint keeps working in retrieval-only mode.
"""

from __future__ import annotations

import logging

import httpx

from src.core.config import settings
from src.schemas.search import SearchResult

logger = logging.getLogger(__name__)

GENERATION_PROMPT_TEMPLATE = """You are a financial analyst assistant specialized in SEC 10-K annual filings.
Answer the question using ONLY the context passages provided below.
IMPORTANT: cite sources using square brackets EXACTLY like this: [1], [2], [3].
Place the citation immediately after the relevant claim. Be concise and factual.
If the context is insufficient to answer, say so explicitly.

Context:
{context}

Question: {query}

Answer:"""


class GenerationService:
    """Generates a cited answer from retrieved 10-K chunks via Ollama.

    Designed to be used as a singleton stored in app.state. Falls back silently
    to returning None on any Ollama failure so retrieval-only mode is preserved.

    Args:
        ollama_base_url: Ollama server base URL. Defaults to settings.OLLAMA_BASE_URL.
        ollama_model: Model name. Defaults to settings.OLLAMA_MODEL.
        client: Optional pre-configured AsyncClient (used for testing).
    """

    # Generation can be slow for large contexts — generous read timeout.
    _DEFAULT_TIMEOUT = httpx.Timeout(connect=3.0, read=60.0, write=5.0, pool=2.0)

    # Maximum number of chunks to include in the context window.
    MAX_CONTEXT_CHUNKS: int = 5

    def __init__(
        self,
        ollama_base_url: str | None = None,
        ollama_model: str | None = None,
        client: httpx.AsyncClient | None = None,
    ) -> None:
        self._base_url = (ollama_base_url or settings.OLLAMA_BASE_URL).rstrip("/")
        self._model = ollama_model or settings.OLLAMA_MODEL
        self._client = client or httpx.AsyncClient(timeout=self._DEFAULT_TIMEOUT)

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    async def generate(
        self,
        query: str,
        results: list[SearchResult],
    ) -> str | None:
        """Generate a cited answer for *query* using *results* as context.

        Args:
            query: The original user question.
            results: Ordered list of retrieved chunks (best first).

        Returns:
            The generated answer string, or None if generation is unavailable
            or fails.
        """
        if not results:
            return None

        context = self._build_context(results[: self.MAX_CONTEXT_CHUNKS])
        prompt = GENERATION_PROMPT_TEMPLATE.format(context=context, query=query)

        try:
            response = await self._client.post(
                f"{self._base_url}/api/generate",
                json={"model": self._model, "prompt": prompt, "stream": False},
            )
            response.raise_for_status()
            data: dict[str, object] = response.json()
            answer = str(data.get("response", "")).strip()
            return answer if answer else None
        except (httpx.TimeoutException, httpx.ConnectError) as exc:
            logger.warning(
                "Ollama unavailable for generation (%s: %s) — returning null answer",
                type(exc).__name__,
                exc,
            )
            return None
        except httpx.HTTPStatusError as exc:
            logger.warning(
                "Ollama returned HTTP %d during generation — returning null answer",
                exc.response.status_code,
            )
            return None

    async def aclose(self) -> None:
        """Release the underlying httpx connection pool."""
        await self._client.aclose()

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _build_context(self, results: list[SearchResult]) -> str:
        """Format retrieved chunks as a numbered context block.

        Args:
            results: Chunks to include (already capped to MAX_CONTEXT_CHUNKS).

        Returns:
            Multi-line string with each chunk prefixed by its citation number.
        """
        parts: list[str] = []
        for i, result in enumerate(results, 1):
            header = f"[{i}] {result.section_title} ({result.section})"
            parts.append(f"{header}\n{result.content}")
        return "\n\n".join(parts)
