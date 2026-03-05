# System Overview

## High-Level Architecture

```mermaid
graph TB
    subgraph "Data Ingestion"
        A[SEC EDGAR API] -->|HTML 10-K| B[Filing Parser]
        B -->|Sections| C[Section Chunker]
        C -->|Chunks| D[Embedding Service]
        D -->|Vectors| E[(PostgreSQL + pgvector)]
    end

    subgraph "Query Processing"
        F[User Query] --> G{Analytical?}
        G -->|Yes| H[HyDE Expansion]
        G -->|No| I[Direct Embedding]
        H --> J[Query Vector]
        I --> J
    end

    subgraph "Hybrid Retrieval"
        J --> K[Dense Search - pgvector]
        F --> L[Sparse Search - BM25]
        K --> M[RRF Fusion]
        L --> M
        M --> N[Ranked Results]
    end

    subgraph "Response"
        N --> O[LLM Generation]
        O --> P[Cited Answer]
    end

    E --> K
    E -->|Startup| L
```

## Component Responsibilities

| Component | Responsibility | Key Tech |
|-----------|---------------|----------|
| EDGAR Client | Ticker→CIK resolution, filing download, caching | httpx, asyncio |
| Filing Parser | iXBRL HTML → sections, metadata extraction | BeautifulSoup, lxml |
| Section Chunker | Overlapping token-based splitting with dual content | tiktoken |
| Embedding Service | Batch sentence embedding, pgvector storage | sentence-transformers |
| BM25 Service | In-memory sparse index, tokenization, scoring | rank-bm25 |
| HyDE Service | Hypothetical document generation, graceful fallback | Ollama/Mistral |
| Retrieval Service | Orchestrates dense + sparse + RRF fusion | Custom RRF |
| FastAPI | REST API, dependency injection, async handlers | FastAPI, Uvicorn |

## Data Flow Summary

**Ingestion** (write path):
Ticker → EDGAR CIK → 10-K HTML → Section Detection → Chunking (220 tokens, 50 overlap) → MiniLM Embedding (384-dim) → pgvector + BM25 Index

**Search** (read path):
Query → [HyDE?] → Dense Search (pgvector cosine) + Sparse Search (BM25) → RRF Fusion → Top-K Results → [LLM Generation]
