"""
Unit Tests — HyDEService and is_analytical_query

All HTTP calls are intercepted via httpx.MockTransport so these tests run
entirely in-memory without a live Ollama server.
"""

from __future__ import annotations

import json
from unittest.mock import MagicMock

import httpx
import pytest

from src.services.hyde_service import (
    ANALYTICAL_KEYWORDS,
    HyDEService,
    is_analytical_query,
)

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_embedding_service(embedding: list[float] | None = None) -> MagicMock:
    """Return a mock EmbeddingService whose embed_texts returns a fixed vector."""
    svc = MagicMock()
    svc.embed_texts.return_value = [embedding or [0.1] * 384]
    return svc


def _make_hyde_service(
    handler: httpx.MockTransport | None = None,
    embedding: list[float] | None = None,
) -> tuple[HyDEService, MagicMock]:
    """Return (HyDEService, embedding_mock) wired with the given transport."""
    embedding_svc = _make_embedding_service(embedding)
    transport = handler or httpx.MockTransport(
        lambda req: httpx.Response(200, json={"response": "hyp doc", "done": True})
    )
    client = httpx.AsyncClient(transport=transport)
    service = HyDEService(
        embedding_service=embedding_svc,
        ollama_base_url="http://ollama-test:11434",
        client=client,
    )
    return service, embedding_svc


# ---------------------------------------------------------------------------
# is_analytical_query
# ---------------------------------------------------------------------------


def test_analytical_query_with_keyword() -> None:
    """A query containing an ANALYTICAL_KEYWORDS token must return True."""
    assert is_analytical_query("compare revenue trends across segments") is True


def test_analytical_query_case_insensitive() -> None:
    """Keyword matching must be case-insensitive."""
    assert is_analytical_query("What is the GROWTH rate of cloud services?") is True


def test_factual_query_returns_false() -> None:
    """A simple factual lookup with no analytical tokens must return False."""
    assert is_analytical_query("What is Apple's revenue in 2024?") is False


def test_empty_query_returns_false() -> None:
    """Empty query must return False (no tokens to match)."""
    assert is_analytical_query("") is False


def test_analytical_single_keyword_suffices() -> None:
    """Any single ANALYTICAL_KEYWORDS match triggers True."""
    for keyword in list(ANALYTICAL_KEYWORDS)[:5]:
        assert is_analytical_query(f"total assets {keyword} last year") is True


def test_factual_query_without_keywords() -> None:
    """Query with no intersection with ANALYTICAL_KEYWORDS returns False."""
    assert is_analytical_query("What is Apple's revenue in 2024?") is False
    assert is_analytical_query("List the subsidiaries of Microsoft.") is False


# ---------------------------------------------------------------------------
# expand_query_to_embedding — factual query (HyDE skipped)
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_factual_query_skips_ollama() -> None:
    """Factual queries must be embedded directly without contacting Ollama."""
    query = "What is Apple's revenue in 2024?"
    query_vec = [0.5] * 384
    embedding_svc = _make_embedding_service(query_vec)

    # Transport that asserts Ollama is never hit
    def fail_if_called(request: httpx.Request) -> httpx.Response:
        raise AssertionError(f"Ollama must not be called for factual queries: {request.url}")

    client = httpx.AsyncClient(transport=httpx.MockTransport(fail_if_called))
    service = HyDEService(
        embedding_service=embedding_svc,
        ollama_base_url="http://ollama-test:11434",
        client=client,
    )

    result = await service.expand_query_to_embedding(query)

    assert result == query_vec
    embedding_svc.embed_texts.assert_called_once_with([query])


# ---------------------------------------------------------------------------
# expand_query_to_embedding — Ollama OK
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ollama_ok_embeds_hypothetical_doc() -> None:
    """When Ollama is available, the hypothetical document must be embedded."""
    hypothetical_doc = "Apple Inc. reported net revenue of $385.7 billion in FY2023..."
    query_vec = [0.1] * 384
    hyp_vec = [0.9] * 384

    embedding_svc: MagicMock = MagicMock()

    def embed_side_effect(texts: list[str]) -> list[list[float]]:
        if texts == [hypothetical_doc]:
            return [hyp_vec]
        return [query_vec]

    embedding_svc.embed_texts.side_effect = embed_side_effect

    def handler(request: httpx.Request) -> httpx.Response:
        if request.url.path == "/api/generate":
            return httpx.Response(200, json={"response": hypothetical_doc, "done": True})
        return httpx.Response(200, json={"models": []})

    client = httpx.AsyncClient(transport=httpx.MockTransport(handler))
    service = HyDEService(
        embedding_service=embedding_svc,
        ollama_base_url="http://ollama-test:11434",
        client=client,
    )

    result = await service.expand_query_to_embedding("compare revenue trends")

    assert result == hyp_vec
    embedding_svc.embed_texts.assert_called_once_with([hypothetical_doc])


# ---------------------------------------------------------------------------
# expand_query_to_embedding — Ollama timeout
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ollama_timeout_falls_back_to_query_embedding() -> None:
    """On timeout, HyDE is skipped gracefully and the original query is embedded."""
    query = "compare revenue trends across segments"
    query_vec = [0.3] * 384
    embedding_svc = _make_embedding_service(query_vec)

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("Timed out reading response")

    client = httpx.AsyncClient(transport=httpx.MockTransport(timeout_handler))
    service = HyDEService(
        embedding_service=embedding_svc,
        ollama_base_url="http://ollama-test:11434",
        client=client,
    )

    result = await service.expand_query_to_embedding(query)

    assert result == query_vec
    embedding_svc.embed_texts.assert_called_once_with([query])


@pytest.mark.asyncio
async def test_ollama_timeout_does_not_raise() -> None:
    """A timeout exception from Ollama must never propagate to the caller."""

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("Connect timed out")

    service, _ = _make_hyde_service(handler=httpx.MockTransport(timeout_handler))

    # Must not raise — fallback is silent
    result = await service.expand_query_to_embedding("how did margins decline")
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# expand_query_to_embedding — Ollama 500
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_ollama_500_falls_back_to_query_embedding() -> None:
    """On HTTP 500, HyDE is skipped gracefully and the original query is embedded."""
    query = "how has risk exposure changed over time"
    query_vec = [0.4] * 384
    embedding_svc = _make_embedding_service(query_vec)

    def error_handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(500, json={"error": "Internal Server Error"})

    client = httpx.AsyncClient(transport=httpx.MockTransport(error_handler))
    service = HyDEService(
        embedding_service=embedding_svc,
        ollama_base_url="http://ollama-test:11434",
        client=client,
    )

    result = await service.expand_query_to_embedding(query)

    assert result == query_vec
    embedding_svc.embed_texts.assert_called_once_with([query])


@pytest.mark.asyncio
async def test_ollama_500_does_not_raise() -> None:
    """An HTTP error from Ollama must never propagate to the caller."""
    service, _ = _make_hyde_service(
        handler=httpx.MockTransport(
            lambda req: httpx.Response(500, json={"error": "server error"})
        )
    )

    result = await service.expand_query_to_embedding("why did operating margins decline")
    assert isinstance(result, list)


# ---------------------------------------------------------------------------
# expand_query_to_embedding — ConnectError
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_connect_error_falls_back_silently() -> None:
    """ConnectError from Ollama must not propagate — fallback to query embedding."""
    query = "why did operating margins decline"
    embedding_svc = _make_embedding_service()

    def connect_error_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    client = httpx.AsyncClient(transport=httpx.MockTransport(connect_error_handler))
    service = HyDEService(
        embedding_service=embedding_svc,
        ollama_base_url="http://ollama-test:11434",
        client=client,
    )

    result = await service.expand_query_to_embedding(query)

    assert isinstance(result, list)
    assert len(result) == 384
    embedding_svc.embed_texts.assert_called_once_with([query])


# ---------------------------------------------------------------------------
# Prompt formatting
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_prompt_contains_query() -> None:
    """The Ollama request body must include the user query in the formatted prompt."""
    query = "how did revenue trends change over three years"
    captured_prompts: list[str] = []

    def capture_handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content)
        captured_prompts.append(body["prompt"])
        return httpx.Response(200, json={"response": "hypothetical passage", "done": True})

    embedding_svc = _make_embedding_service()
    client = httpx.AsyncClient(transport=httpx.MockTransport(capture_handler))
    service = HyDEService(
        embedding_service=embedding_svc,
        ollama_base_url="http://ollama-test:11434",
        client=client,
    )

    await service.expand_query_to_embedding(query)

    assert len(captured_prompts) == 1
    assert query in captured_prompts[0]


@pytest.mark.asyncio
async def test_prompt_uses_configured_model() -> None:
    """The Ollama request must reference the configured model name."""
    captured_bodies: list[dict[str, object]] = []

    def capture_handler(request: httpx.Request) -> httpx.Response:
        captured_bodies.append(json.loads(request.content))
        return httpx.Response(200, json={"response": "passage", "done": True})

    embedding_svc = _make_embedding_service()
    client = httpx.AsyncClient(transport=httpx.MockTransport(capture_handler))
    service = HyDEService(
        embedding_service=embedding_svc,
        ollama_base_url="http://ollama-test:11434",
        ollama_model="mistral-custom",
        client=client,
    )

    await service.expand_query_to_embedding("compare revenue trends")

    assert len(captured_bodies) == 1
    assert captured_bodies[0]["model"] == "mistral-custom"


# ---------------------------------------------------------------------------
# is_available
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_is_available_returns_true_on_200() -> None:
    """is_available must return True when /api/tags returns 200."""
    service, _ = _make_hyde_service(
        handler=httpx.MockTransport(lambda req: httpx.Response(200, json={"models": []}))
    )
    assert await service.is_available() is True


@pytest.mark.asyncio
async def test_is_available_returns_false_on_connect_timeout() -> None:
    """is_available must return False on connection timeout."""

    def timeout_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectTimeout("Connection timed out")

    service, _ = _make_hyde_service(handler=httpx.MockTransport(timeout_handler))
    assert await service.is_available() is False


@pytest.mark.asyncio
async def test_is_available_returns_false_on_error_status() -> None:
    """is_available must return False when Ollama returns a non-2xx status."""
    service, _ = _make_hyde_service(
        handler=httpx.MockTransport(
            lambda req: httpx.Response(503, json={"error": "service unavailable"})
        )
    )
    assert await service.is_available() is False


@pytest.mark.asyncio
async def test_is_available_returns_false_on_connect_error() -> None:
    """is_available must return False when the connection is refused."""

    def connect_error_handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("Connection refused")

    service, _ = _make_hyde_service(handler=httpx.MockTransport(connect_error_handler))
    assert await service.is_available() is False
