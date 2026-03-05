# ADR-005: HyDE Only on Analytical Queries

## Status
Accepted

## Context
HyDE (Hypothetical Document Embeddings) generates a hypothetical answer
passage via LLM, then embeds that passage instead of the raw query.
This can improve recall for abstract queries but adds latency (LLM call)
and may hurt precision for factual lookups.

## Decision
Apply HyDE expansion only when the query is classified as "analytical"
(contains keywords like compare, trend, growth, risk, impact, etc.).
Factual queries are embedded directly.

## Rationale
- **Factual queries are precise**: "What is Apple's revenue in 2024?" has
  exact lexical matches in the corpus. HyDE would generate a paraphrase
  that may drift from the actual phrasing in the filing
- **Analytical queries benefit from expansion**: "How did risk exposure
  change over time?" matches poorly against specific filing passages.
  A hypothetical 10-K paragraph bridges the vocabulary gap
- **Latency budget**: HyDE adds 1-3s (Ollama generation). Acceptable for
  complex analytical queries, not for simple lookups
- **Graceful degradation**: When Ollama is unavailable, HyDE silently falls
  back to direct query embedding. No user-facing errors

## Consequences
### Positive
- Fast path for factual queries (~12ms hybrid without HyDE)
- Improved recall on analytical queries where dense-only struggles
- No dependency on Ollama for core functionality

### Negative
- Keyword-based classification is a heuristic — some analytical queries
  may be misclassified as factual (false negatives)
- Cannot A/B test HyDE benefit without the evaluation harness (Sprint 4)
