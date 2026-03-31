"""
Unit Tests — GenerationService

All HTTP calls are intercepted via httpx.MockTransport so these tests run
entirely in-memory without a live Ollama server.
"""

from __future__ import annotations

import json
import uuid
from unittest.mock import MagicMock

import httpx
import pytest

from src.services.generation import GenerationService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_service(handler: httpx.MockTransport) -> GenerationService:
    """Return a GenerationService wired with the given mock transport."""
    client = httpx.AsyncClient(transport=handler)
    return GenerationService(
        ollama_base_url="http://ollama-test:11434",
        ollama_model="mistral",
        client=client,
    )


def _make_result(content: str = "Revenue was $100B.", index: int = 1) -> MagicMock:
    """Return a minimal SearchResult mock."""
    result = MagicMock()
    result.chunk_id = uuid.uuid4()
    result.content = content
    result.section = "ITEM_7"
    result.section_title = f"MD&A result {index}"
    return result


def _ollama_response(text: str) -> httpx.Response:
    """Build a fake Ollama /api/generate response."""
    body = json.dumps({"response": text, "done": True})
    return httpx.Response(200, content=body.encode())


# ---------------------------------------------------------------------------
# Tests — happy path
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_returns_answer() -> None:
    """generate() returns the LLM response text when Ollama succeeds."""
    expected = "Apple's revenue was $391B in FY2024 [1]."

    def handler(request: httpx.Request) -> httpx.Response:
        return _ollama_response(expected)

    svc = _make_service(httpx.MockTransport(handler))
    results = [_make_result("Apple revenue $391B.")]

    answer = await svc.generate("What was Apple's revenue?", results)
    assert answer == expected


@pytest.mark.asyncio
async def test_generate_strips_whitespace() -> None:
    """generate() strips leading/trailing whitespace from the model output."""

    def handler(request: httpx.Request) -> httpx.Response:
        return _ollama_response("  Answer with spaces.  \n")

    svc = _make_service(httpx.MockTransport(handler))
    answer = await svc.generate("query", [_make_result()])

    assert answer == "Answer with spaces."


@pytest.mark.asyncio
async def test_generate_caps_context_to_max_chunks() -> None:
    """generate() sends at most MAX_CONTEXT_CHUNKS chunks to Ollama."""
    captured_body: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured_body.update(json.loads(request.content))
        return _ollama_response("ok")

    svc = _make_service(httpx.MockTransport(handler))
    # Send 10 results — only MAX_CONTEXT_CHUNKS should appear in prompt
    results = [_make_result(f"chunk {i}", i) for i in range(10)]
    await svc.generate("query", results)

    prompt = str(captured_body.get("prompt", ""))
    # The prompt should contain [5] but not [6]
    assert f"[{GenerationService.MAX_CONTEXT_CHUNKS}]" in prompt
    assert f"[{GenerationService.MAX_CONTEXT_CHUNKS + 1}]" not in prompt


# ---------------------------------------------------------------------------
# Tests — empty results
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_returns_none_for_empty_results() -> None:
    """generate() returns None immediately when no results are provided."""
    called = False

    def handler(request: httpx.Request) -> httpx.Response:
        nonlocal called
        called = True
        return _ollama_response("should not be called")

    svc = _make_service(httpx.MockTransport(handler))
    answer = await svc.generate("query", [])

    assert answer is None
    assert not called, "Ollama should not be called when results are empty"


# ---------------------------------------------------------------------------
# Tests — graceful degradation
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_generate_returns_none_on_connection_error() -> None:
    """generate() returns None and does not raise when Ollama is unreachable."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    svc = _make_service(httpx.MockTransport(handler))
    answer = await svc.generate("query", [_make_result()])

    assert answer is None


@pytest.mark.asyncio
async def test_generate_returns_none_on_timeout() -> None:
    """generate() returns None and does not raise on read timeout."""

    def handler(request: httpx.Request) -> httpx.Response:
        raise httpx.ReadTimeout("read timeout")

    svc = _make_service(httpx.MockTransport(handler))
    answer = await svc.generate("query", [_make_result()])

    assert answer is None


@pytest.mark.asyncio
async def test_generate_returns_none_on_http_error() -> None:
    """generate() returns None when Ollama responds with a non-2xx status."""

    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(503, content=b"Service Unavailable")

    svc = _make_service(httpx.MockTransport(handler))
    answer = await svc.generate("query", [_make_result()])

    assert answer is None


@pytest.mark.asyncio
async def test_generate_returns_none_for_empty_model_response() -> None:
    """generate() returns None when Ollama returns an empty string."""

    def handler(request: httpx.Request) -> httpx.Response:
        return _ollama_response("   ")

    svc = _make_service(httpx.MockTransport(handler))
    answer = await svc.generate("query", [_make_result()])

    assert answer is None


# ---------------------------------------------------------------------------
# Tests — context building
# ---------------------------------------------------------------------------


def test_build_context_numbers_chunks() -> None:
    """_build_context() produces [1], [2] prefixes for each chunk."""
    svc = GenerationService.__new__(GenerationService)
    results = [_make_result("chunk A", 1), _make_result("chunk B", 2)]
    context = svc._build_context(results)

    assert "[1]" in context
    assert "[2]" in context
    assert "chunk A" in context
    assert "chunk B" in context
