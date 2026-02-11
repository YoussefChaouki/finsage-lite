# ==============================================================================
# FinSage-Lite — Developer Task Automation
# Usage: make <target>
# Run `make help` to see all available targets.
# ==============================================================================

.PHONY: help setup install run test test-unit test-int \
        lint format type-check check \
        docker-up docker-down docker-logs rebuild \
        db-shell migrate seed evaluate evaluate-report clean

# ==============================================================================
# Help
# ==============================================================================

help: ## Show this help message
	@echo "📊 FinSage-Lite — Available Targets"
	@echo "━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━"
	@grep -E '^[a-zA-Z_-]+:.*?## .*$$' $(MAKEFILE_LIST) | \
		awk 'BEGIN {FS = ":.*?## "}; {printf "  \033[36m%-20s\033[0m %s\n", $$1, $$2}'

# ==============================================================================
# Setup & Installation
# ==============================================================================

setup: install ## Full dev setup: install deps + pre-commit hooks
	pre-commit install
	@echo "✓ Dev environment ready"

install: ## Install project in editable mode with dev dependencies
	pip install -e ".[dev]"

# ==============================================================================
# Local Development (no Docker required for API)
# ==============================================================================

run: ## Start API on :8000 (hot-reload)
	uvicorn src.api.main:app --host 0.0.0.0 --port 8000 --reload

# ==============================================================================
# Testing
# ==============================================================================

test: ## Run all tests (unit + integration)
	pytest tests/ -v

test-unit: ## Run unit tests only (no Docker needed)
	pytest tests/unit/ -v --tb=short

test-int: ## Run integration tests (requires: make docker-up)
	pytest tests/integration/ -v

# ==============================================================================
# Code Quality
# ==============================================================================

lint: ## Run linter (ruff) + type checker (mypy)
	ruff check --fix .
	mypy src/ --strict

format: ## Auto-format code with ruff
	ruff format .

type-check: ## Run type checker only
	mypy src/ --strict

check: ## Quick pre-commit validation (format + lint + unit tests)
	@echo "━━━ Formatting ━━━"
	ruff format --check .
	@echo "━━━ Linting ━━━"
	ruff check .
	@echo "━━━ Type Checking ━━━"
	mypy src/ --strict
	@echo "━━━ Unit Tests ━━━"
	pytest tests/unit/ -v --tb=short
	@echo ""
	@echo "✓ All checks passed"

# ==============================================================================
# Docker Operations
# ==============================================================================

docker-up: ## Start full Docker stack (API + UI + DB)
	docker compose up -d
	@echo ""
	@echo "✓ FinSage-Lite is running:"
	@echo "   UI:   http://localhost:8501"
	@echo "   API:  http://localhost:8000"
	@echo "   Docs: http://localhost:8000/docs"

docker-down: ## Stop all Docker services
	docker compose down

docker-logs: ## Tail all Docker service logs
	docker compose logs -f

rebuild: ## Rebuild and restart all Docker services
	docker compose down
	docker compose up -d --build

# ==============================================================================
# Database
# ==============================================================================

db-shell: ## Open psql shell in the database container
	docker compose exec db psql -U finsage -d finsage_db

migrate: ## Apply all pending Alembic migrations
	POSTGRES_HOST=localhost alembic upgrade head

# ==============================================================================
# Evaluation
# ==============================================================================

seed: ## Ingest demo data (AAPL, MSFT, GOOGL)
	python scripts/seed_demo_data.py

evaluate: ## Run RAG evaluation harness
	python evaluation/harness.py

evaluate-report: ## Generate evaluation report
	python evaluation/report_generator.py

# ==============================================================================
# Cleanup
# ==============================================================================

clean: ## Remove build artifacts, caches, and temp files
	find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".pytest_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".mypy_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name ".ruff_cache" -exec rm -rf {} + 2>/dev/null || true
	find . -type d -name "*.egg-info" -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
	rm -rf dist/ build/ htmlcov/ .coverage
	@echo "✓ Cleaned"
