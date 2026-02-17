# FinSage-Lite
## Project Overview
SEC 10-K filing analysis RAG system. Extends CITADEL RAG pipeline for financial domain.
Local-first (privacy), hybrid retrieval (BM25 + dense), scientific evaluation.
## Architecture
User Query → HyDE Expansion → Hybrid Retrieval (BM25 + pgvector RRF)
→ Context Assembly → LLM Generation (Ollama/Mistral) → Cited Response
SEC Filings: EDGAR API → PDF Parser → Section-Aware Chunker → Embeddings → pgvector
## Project Structure
finsage-lite/
├── src/
│ ├── api/
│ │ ├── routers/ # FastAPI route handlers
│ │ │ ├── document.py # Document upload/management
│ │ │ ├── search.py # Search endpoint (dense/sparse/hybrid)
│ │ │ └── health.py # Health check
│ │ └── dependencies.py # Shared dependencies
│ ├── services/
│ │ ├── ingestion.py # SEC EDGAR + PDF processing
│ │ ├── chunking.py # Section-aware chunking
│ │ ├── embedding.py # Embedding generation
│ │ ├── search.py # Hybrid retrieval logic
│ │ ├── hyde.py # HyDE query expansion
│ │ └── generation.py # LLM generation with citations
│ ├── models/ # SQLAlchemy models
│ ├── schemas/ # Pydantic request/response schemas
│ ├── core/
│ │ ├── config.py # pydantic-settings configuration
│ │ ├── database.py # Async DB session management
│ │ └── logging.py # Logging configuration
│ └── clients/
│ ├── edgar.py # SEC EDGAR API client
│ └── ollama.py # Ollama client with fallback
├── tests/
│ ├── unit/
│ ├── integration/
│ └── conftest.py
├── evaluation/
│ ├── harness.py # Evaluation runner
│ ├── datasets/ # FinanceBench + custom
│ └── reports/ # Auto-generated reports
├── streamlit_app/
│ └── app.py
├── docker-compose.yml
├── Dockerfile
├── Makefile
├── pyproject.toml
├── CLAUDE.md # This file
└── README.md
## Code Conventions
- Python 3.11+, async/await everywhere
- Type hints: Mypy strict mode (`--strict`)
- Docstrings: Google-style on all public functions
- Formatting: Ruff (line-length 99)
- No print() — use `logging` module
- No hardcoded values — use `src/core/config.py`
- No bare try/except — always specify exception type
- No mutable default arguments
## Patterns
- **Repository pattern**: All DB access through repository classes in `src/repositories/`
- **Service layer**: Business logic in `src/services/`, never in routers
- **Pydantic schemas**: All request/response validation via schemas
- **Dependency injection**: FastAPI `Depends()` for shared resources
- **Async throughout**: All I/O operations must be async
- **Graceful degradation**: System must work without Ollama (return retrieved chunks only)
## Git Conventions
- Branches: `feat/`, `fix/`, `docs/`, `test/`, `refactor/`
- Commits: Conventional format
- `feat: add hybrid search endpoint`
- `fix: handle empty SEC EDGAR response`
- `docs: update architecture diagram`
- `test: add integration tests for chunking`
- `refactor: extract RRF scoring to utility`
- Always run `make lint && make test` before committing
## Useful Commands
```bash
make test # Run all tests
make test-unit make test-int make lint # Run unit tests only
# Run integration tests
# Ruff check + format
make type-check # Mypy strict
make docker-up # Start all services
make docker-down # Stop all services
make migrate # Run Alembic migrations
make evaluate # Run evaluation harness
make evaluate-report # Generate markdown report
```
## Do NOT
- Modify existing Alembic migrations
- Add dependencies without adding them to pyproject.toml
- Use synchronous DB calls
- Commit .env files or any secrets
- Use `SELECT *` in SQL queries
- Skip writing tests for new features