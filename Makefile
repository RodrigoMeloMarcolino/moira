.PHONY: lint test test-unit test-integration

lint:
	uv run ruff check .
	uv run ruff format --check .
	uv run mypy app

test-unit:
	uv run pytest -m "not integration"

test-integration:
	uv run python scripts/run_integration_tests.py

test: test-unit test-integration
