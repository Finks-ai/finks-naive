.PHONY: help install install-dev format lint type-check security test test-cov clean pre-commit quality

help:
	@echo "Available commands:"
	@echo "  make install      - Install production dependencies"
	@echo "  make install-dev  - Install all dependencies including dev tools"
	@echo "  make format       - Format code with black and isort"
	@echo "  make lint         - Run ruff linter"
	@echo "  make type-check   - Run mypy type checker"
	@echo "  make security     - Run security checks with bandit and safety"
	@echo "  make test         - Run tests"
	@echo "  make test-cov     - Run tests with coverage"
	@echo "  make clean        - Clean up cache files"
	@echo "  make pre-commit   - Install and run pre-commit hooks"
	@echo "  make quality      - Run all code quality checks"

install:
	uv sync

install-dev:
	uv sync --all-extras

format:
	@echo "Running isort..."
	uv run isort app tests
	@echo "Running black..."
	uv run black app tests
	@echo "Running ruff format..."
	uv run ruff format app tests

lint:
	@echo "Running ruff linter..."
	uv run ruff check app tests --fix
	@echo "Checking for common issues..."
	uv run ruff check app tests --statistics

type-check:
	@echo "Running mypy..."
	uv run mypy app

security:
	@echo "Running bandit security linter..."
	uv run bandit -r app -f json -o bandit-report.json || true
	@echo "Checking for known vulnerabilities..."

test:
	uv run pytest tests -v

test-cov:
	uv run pytest tests --cov=app --cov-report=html --cov-report=term-missing
	@echo "Coverage report generated in htmlcov/"

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type f -name "*.pyc" -delete
	find . -type d -name ".pytest_cache" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +
	find . -type d -name ".ruff_cache" -exec rm -rf {} +
	find . -type d -name "htmlcov" -exec rm -rf {} +
	find . -type f -name ".coverage" -delete
	find . -type f -name "bandit-report.json" -delete

pre-commit:
	uv run pre-commit install
	uv run pre-commit run --all-files

quality: format lint type-check security test-cov
	@echo "All quality checks completed!"
