.PHONY: install lint typecheck test test-cov local-up local-down clean

install:
	pip install -e ".[dev]"

lint:
	ruff check src/ tests/
	ruff format --check src/ tests/

format:
	ruff format src/ tests/

typecheck:
	mypy src/

test:
	pytest tests/ -v --tb=short --strict-markers

test-cov:
	pytest tests/ -v --tb=short --strict-markers --cov=cacp --cov-report=term-missing

local-up:
	docker compose -f infra/local/docker-compose.yml up -d --build

local-down:
	docker compose -f infra/local/docker-compose.yml down -v

clean:
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	rm -rf .mypy_cache .pytest_cache .ruff_cache dist/ build/ *.egg-info
