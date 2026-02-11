# ==============================================================================
# FinSage-Lite - Production Dockerfile
# Multi-stage optimized build for FastAPI + async SQLAlchemy + RAG pipeline
# ==============================================================================

FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=off \
    PIP_DISABLE_PIP_VERSION_CHECK=on \
    PYTHONPATH=/app

WORKDIR /app

# Copy dependency manifest first (Docker layer caching)
COPY pyproject.toml .

# Install dependencies
# 1. CPU-only PyTorch (saves ~1.5GB vs full CUDA build)
# 2. Core FastAPI + DB stack
# 3. RAG pipeline dependencies (sentence-transformers, BM25, langchain)
RUN pip install --upgrade pip && \
    pip install torch --index-url https://download.pytorch.org/whl/cpu && \
    pip install -e ".[dev]"

# Copy source code
COPY src/ src/
COPY tests/ tests/
COPY scripts/ scripts/
COPY evaluation/ evaluation/
COPY alembic/ alembic/
COPY alembic.ini .

# Pre-download embedding model (cached in image layer, ~90MB)
# Avoids cold-start download on first request
RUN python -c "from sentence_transformers import SentenceTransformer; SentenceTransformer('all-MiniLM-L6-v2')"

# Security: Run as non-root user in production
RUN useradd -m finsage
USER finsage

EXPOSE 8000

CMD ["uvicorn", "src.api.main:app", "--host", "0.0.0.0", "--port", "8000"]
