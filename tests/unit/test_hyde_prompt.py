"""
Unit Tests — HYDE_PROMPT_TEMPLATE

Validates the prompt template structure to guard against accidental modifications
that would break HyDE generation quality or cause string formatting errors.
"""

from __future__ import annotations

from src.services.hyde_service import HYDE_PROMPT_TEMPLATE


def test_template_formats_without_error() -> None:
    """HYDE_PROMPT_TEMPLATE.format(query=...) must not raise any exception."""
    result = HYDE_PROMPT_TEMPLATE.format(query="test query about Apple revenue")
    assert isinstance(result, str)
    assert len(result) > 0


def test_template_embeds_query_verbatim() -> None:
    """The formatted template must contain the exact query string."""
    query = "What is Apple's revenue in 2024?"
    result = HYDE_PROMPT_TEMPLATE.format(query=query)
    assert query in result


def test_template_references_10k() -> None:
    """The template must reference '10-K' to establish financial document context."""
    assert "10-K" in HYDE_PROMPT_TEMPLATE


def test_template_references_financial_analyst() -> None:
    """The template must establish the financial analyst persona."""
    assert "financial analyst" in HYDE_PROMPT_TEMPLATE


def test_template_requests_hypothetical_passage() -> None:
    """The template must include 'Hypothetical passage' to signal the generation style."""
    assert "Hypothetical passage" in HYDE_PROMPT_TEMPLATE


def test_template_has_single_query_placeholder() -> None:
    """The template must contain exactly one {query} placeholder."""
    assert HYDE_PROMPT_TEMPLATE.count("{query}") == 1


def test_template_query_appears_once_after_format() -> None:
    """The formatted query must appear exactly once in the output."""
    query = "unique-marker-xyz-12345"
    result = HYDE_PROMPT_TEMPLATE.format(query=query)
    assert result.count(query) == 1


def test_different_queries_produce_different_prompts() -> None:
    """Different queries must produce different formatted prompts."""
    prompt_a = HYDE_PROMPT_TEMPLATE.format(query="revenue trends")
    prompt_b = HYDE_PROMPT_TEMPLATE.format(query="risk factors")
    assert prompt_a != prompt_b


def test_template_mentions_annual_report() -> None:
    """The template must reference 'annual report' to anchor the generation style."""
    assert "annual report" in HYDE_PROMPT_TEMPLATE


def test_template_mentions_financial_terminology() -> None:
    """The template must request financial terminology in the generated output."""
    assert "financial terminology" in HYDE_PROMPT_TEMPLATE
