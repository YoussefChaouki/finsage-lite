# FinSage-Lite

SEC 10-K filing analysis system with hybrid retrieval (BM25 + dense vectors + RRF), powered by local embeddings and PostgreSQL/pgvector.

## Architecture

```
SEC EDGAR ──► HTML Parser ──► Section Chunker ──► MiniLM Embeddings ──► pgvector
                                                                           │
                                                        FastAPI ◄── Hybrid Search
                                                      (BM25 + cosine + RRF)
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
| UI | Streamlit |

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- (Optional) Ollama for LLM generation

### Installation

```bash
git clone <repository-url>
cd finsage-lite

python3 -m venv venv
source venv/bin/activate

make install   # pip install -e ".[dev]"
make setup     # + pre-commit hooks
```

### Running

```bash
cp .env.example .env
# Edit .env with your config (EDGAR_USER_AGENT email is required by SEC)

make docker-up
```

| Service | URL |
|---|---|
| API | http://localhost:8000 |
| Swagger docs | http://localhost:8000/docs |
| UI | http://localhost:8501 |

### Ingest a filing

```bash
curl -X POST http://localhost:8000/api/v1/documents/ingest \
  -H "Content-Type: application/json" \
  -d '{"ticker": "AAPL", "fiscal_year": 2024}'
```

## Project Structure

```
src/
├── api/
│   └── routers/         # health, document endpoints
├── clients/
│   └── edgar.py         # SEC EDGAR HTTP client (async)
├── core/
│   ├── config.py        # Pydantic Settings
│   └── database.py      # AsyncSession factory
├── models/
│   ├── document.py      # Document ORM (documents table)
│   └── chunk.py         # Chunk ORM + pgvector embedding column
├── repositories/
│   ├── document.py      # Document CRUD
│   └── chunk.py         # Chunk CRUD + cosine similarity search
├── schemas/             # Pydantic request/response models
├── services/
│   ├── ingestion.py     # Full pipeline orchestrator
│   ├── parsing.py       # 10-K HTML → section splitter
│   ├── chunking.py      # Section-aware text chunking
│   └── embedding.py     # MiniLM batch embed + pgvector store
tests/
├── unit/                # 86+ tests, no Docker needed
└── integration/         # Requires running Docker stack
```

## Development

```bash
make test           # All tests (unit + integration)
make test-unit      # Unit tests only
make test-int       # Integration tests (requires docker-up)

make format         # ruff format
make lint           # ruff check --fix + mypy --strict
make check          # format + lint + type-check + unit tests

make db-shell       # psql into the database
make migrate        # Alembic migrations
make clean          # Remove __pycache__, .mypy_cache, etc.
```

## Configuration

Key settings via `.env` (see [.env.example](.env.example)):

| Variable | Default | Description |
|---|---|---|
| `EDGAR_USER_AGENT` | — | Required by SEC (format: `App (email)`) |
| `EMBEDDING_MODEL` | `all-MiniLM-L6-v2` | Sentence-transformers model |
| `CHUNK_SIZE` | `220` | Tokens per chunk (fits MiniLM 256-token window with prefix) |
| `CHUNK_OVERLAP` | `50` | Token overlap between chunks |
| `POSTGRES_*` | see file | Database connection |

## License

MIT
