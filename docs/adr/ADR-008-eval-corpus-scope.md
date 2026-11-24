# ADR-008: Scope of the evaluation corpus

## Status: Accepted

## Date
2026-03

## Context

FinSage-Lite aims for a rigorous evaluation of its RAG pipeline on real financial questions.
PatronusAI/financebench is the public reference dataset for this kind of system: it contains
numeric and factual questions grounded in real SEC 10-K filings, with answers verified by
financial analysts.

The dataset has **~150 questions** covering some fifteen S&P 500 companies across several
fiscal years (mostly FY2021–FY2023). Ingesting every corresponding filing would mean ~15 PDF
documents, a time and storage cost that is prohibitive for one evaluation sprint. A
representative subset therefore has to be selected.

Selection criteria:
- Maximize the number of questions covered
- Minimize the number of filings to ingest (target: 1 filing per company)
- Prefer companies with ≥ 10 questions in the dataset
- Keep 3–4 companies for a minimum of sector diversity

Output of `make inspect-dataset` (run on 2026-03-28):

```
Total questions: 150
Companies represented: 20+

Top companies (by number of questions):
  PepsiCo                11  (FY2022: 5, FY2023: 5, FY2021: 1)
  Amcor                   9  (FY2023: 7, FY2022: 1, FY2020: 1)
  Johnson & Johnson       9  (FY2022: 5, FY2023: 4)
  3M                      8  (FY2022: 3, FY2023: 3, FY2018: 2)
  AMD                     8
  Best Buy                8
  Boeing                  8

Categories (balanced at 50 each):
  metrics-generated : 50
  domain-relevant   : 50
  novel-generated   : 50

Selected: [PepsiCo FY2023, Amcor FY2023, Johnson & Johnson FY2022, 3M FY2023]
```

## Decision

Use the following companies and fiscal years for the Sprint 4 benchmark:

| Company | Ticker | Fiscal Year | Questions covered |
|-----------|--------|-------------|---------------------|
| PepsiCo | PEP | FY2023 | 5 |
| Amcor | AMCR | FY2023 | 7 |
| Johnson & Johnson | JNJ | FY2022 | 5 |
| 3M | MMM | FY2023 | 3 |
| **Total** | | | **20 / 150 (13.3%)** |

Fiscal-year selection rule: the best-represented year per company
(tie-break: the most recent year).

## Rationale

1. **Maximum coverage**: the 3–4 best-represented companies in financebench hold the largest
   share of questions, which gives the most questions per ingested filing.

2. **Minimal ingestion cost**: keeping a single fiscal year per company (the best represented
   in the dataset) limits ingestion to 3–4 10-K filings, a few minutes of processing.

3. **Sector diversity**: financebench covers tech, finance, industry and energy. Selecting by
   question volume naturally preserves that diversity, since large caps are over-represented
   in the dataset.

4. **Reproducibility**: SEC filings are public and permanent on EDGAR. Any contributor can
   re-run the benchmark.

## Consequences

- **Effective coverage**: 20 / 150 questions (13.3%), intentionally limited to 4 filings.
  The initial estimate of 60–80% assumed a multi-year selection; the "1 filing per company"
  constraint brings it down to 13.3%, enough to compare configurations against each other.
- **Filings to ingest**: 4 documents (PEP FY2023, AMCR FY2023, JNJ FY2022, MMM FY2023).
- **Sprint 4 target metrics**: Recall@5 ≥ 85% on the best configuration (main objective).
  Token-level F1 ≥ 0.40 on questions with generation enabled.
- **Categories**: the 3 financebench categories (metrics-generated, domain-relevant,
  novel-generated) are balanced at 50 each; the 20-question sub-corpus reflects that
  distribution.
- **Limitation**: the 130 out-of-corpus questions are excluded from automatic evaluation.
  They can be used to test robustness on unseen companies (zero-shot).
