# FinSage-Lite

SEC 10-K filing analysis system with hybrid retrieval (BM25 + dense vectors + RRF), local LLM synthesis, and a production-ready React frontend.

## Screenshots

> [Screenshot coming soon]

## Quick Start

```bash
git clone <repository-url>
cd finsage-lite

cp .env.example .env
# Edit .env — EDGAR_USER_AGENT (format: "App Name email@example.com") is required by SEC

make docker-up
```

| Service      | URL                          |
|---|---|
| Frontend     | http://localhost:5173         |
| API          | http://localhost:8000         |
| API docs     | http://localhost:8000/docs    |

```bash
make seed   # Ingest demo data (AAPL, MSFT, GOOGL)
```

## Architecture

```
SEC EDGAR ──► HTML Parser ──► Section Chunker ──► MiniLM Embeddings ──► pgvector
                                                                           │
                                                 FastAPI ◄── Hybrid Search (BM25 + cosine + RRF)
                                                    │
                                              Ollama (Mistral)
                                                    │
                                            React Frontend ◄── Cited Answer + Source Cards
```

**Pipeline**: Ticker → EDGAR CIK resolution → 10-K download → section-aware HTML parsing → overlapping chunking (220 tokens, 50 overlap) → MiniLM-L6-v2 embeddings (384-dim) → pgvector storage with IVFFlat cosine index.

## Tech Stack

| Layer | Technology |
|---|---|
| API | FastAPI + Uvicorn |
| Database | PostgreSQL + pgvector |
| Embeddings | sentence-transformers `all-MiniLM-L6-v2` (384-dim) |
| ORM | SQLAlchemy 2.0 async (asyncpg) |
| Migrations | Alembic |
| Sparse search | rank-bm25 |
| HTML parsing | BeautifulSoup4 + lxml |
| LLM (optional) | Ollama (Mistral) |
| Frontend | React 19 + Vite 8 |
| UI components | shadcn/ui + Radix UI |
| Styling | Tailwind CSS 3 (dark theme) |
| Animations | Framer Motion 12 |
| State | Zustand + TanStack Query |

## Project Structure

```
src/                        # FastAPI backend
├── api/routers/            # health, document, search endpoints
├── clients/edgar.py        # SEC EDGAR HTTP client (async)
├── core/                   # config, database, logging
├── models/                 # SQLAlchemy ORM (documents, chunks)
├── repositories/           # DB access layer
├── schemas/                # Pydantic request/response models
└── services/               # ingestion, chunking, embedding, search, generation

frontend/src/               # React frontend
├── components/             # UI components (search, browse, documents, layout)
├── hooks/                  # useSearch, useBrowse, useDocuments, useIngest
├── pages/                  # SearchPage, BrowsePage, DocumentsPage
├── store/appStore.ts       # Zustand global state
└── lib/                    # api client, types, utils

tests/
├── unit/                   # 86+ tests, no Docker needed
└── integration/            # Requires running Docker stack
```

## Development

```bash
# Backend
make test           # All tests (unit + integration)
make test-unit      # Unit tests only
make format         # ruff format
make lint           # ruff check --fix + mypy --strict
make check          # format + lint + type-check + unit tests + frontend types

# Frontend
make frontend-install   # npm ci
make frontend-dev       # Vite dev server on :5173 (outside Docker)
make frontend-build     # Build production assets to frontend/dist/
make frontend-check     # TypeScript type-check only

# Database
make db-shell       # psql into the database
make migrate        # Alembic migrations

# Production build
BUILD_TARGET=production docker compose up -d --build
```

## Configuration

Key settings via `.env` (see [.env.example](.env.example)):

| Variable | Default | Description |
|---|---|---|
| `EDGAR_USER_AGENT` | — | Required by SEC (format: `App (email)`) |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers model |
| `CHUNK_SIZE` | `220` | Tokens per chunk |
| `CHUNK_OVERLAP` | `50` | Token overlap between chunks |
| `OLLAMA_BASE_URL` | `http://localhost:11434` | Ollama endpoint for LLM synthesis |
| `POSTGRES_*` | see file | Database connection |

## Architecture & Decisions

- **[System Overview](docs/architecture/system-overview.md)** — Component diagram and data flow
- **[Scaling Considerations](docs/architecture/scaling-considerations.md)** — Production scaling paths
- **[ADRs](docs/adr/)** — Key technical decisions with context and tradeoffs

## License

MIT
