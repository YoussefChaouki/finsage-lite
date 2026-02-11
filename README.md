# FinSage-Lite

SEC 10-K filing analysis RAG system with hybrid retrieval (BM25 + dense + RRF).

## Features

- **Local-first**: Privacy-focused with local document storage
- **Hybrid Retrieval**: BM25 sparse + dense vector search with Reciprocal Rank Fusion
- **SEC EDGAR Integration**: Direct filing ingestion from SEC EDGAR API
- **Table-Aware**: Special handling for financial tables
- **HyDE Query Expansion**: Optional query enhancement for analytical questions
- **Scientific Evaluation**: Built-in evaluation harness with FinanceBench dataset

## Quick Start

### Prerequisites

- Python 3.11+
- Docker & Docker Compose
- (Optional) Ollama for LLM generation

### Installation

```bash
# Clone the repository
git clone <repository-url>
cd finsage-lite

# Create and activate virtual environment
python3 -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
make install

# (Optional) Install pre-commit hooks
make setup
```

### Running the Application

```bash
# Copy environment template
cp .env.example .env

# Edit .env with your configuration (database credentials, etc.)

# Start all services (API + UI + PostgreSQL)
make docker-up

# The application will be available at:
# - API:  http://localhost:8000
# - Docs: http://localhost:8000/docs
# - UI:   http://localhost:8501
```

### Development

```bash
# Run tests
make test
make test-unit      # Unit tests only
make test-int       # Integration tests only

# Code quality
make lint           # Run linter + type checker
make format         # Auto-format code
make check          # Pre-commit validation

# Database
make migrate        # Run Alembic migrations
make db-shell       # Open psql shell

# Cleanup
make clean          # Remove build artifacts
make docker-down    # Stop all services
```

## Project Structure

```
finsage-lite/
├── src/
│   ├── api/           # FastAPI routers
│   ├── services/      # Business logic
│   ├── models/        # SQLAlchemy models
│   ├── schemas/       # Pydantic schemas
│   ├── repositories/  # Data access layer
│   ├── core/          # Configuration & database
│   └── clients/       # External API clients
├── tests/
│   ├── unit/          # Unit tests
│   └── integration/   # Integration tests
├── evaluation/        # RAG evaluation harness
├── scripts/           # Utility scripts
└── streamlit_app/     # Streamlit UI
```

## License

MIT
