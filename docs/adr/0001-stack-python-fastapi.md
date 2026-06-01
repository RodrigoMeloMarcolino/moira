# ADR 0001 - Stack Python/FastAPI

## Status

Accepted

## Context

Moira is a scheduling SaaS backend that needs a productive, testable API stack with strong support for PostgreSQL, async I/O, automated testing, and future AI-oriented integrations.

The project is also intended to deepen practical experience with modern Python backend development.

## Decision

Use Python 3.12, FastAPI, PostgreSQL, SQLAlchemy 2.x async, asyncpg, Alembic, Pytest, Ruff, Mypy, Docker, and Docker Compose as the initial backend stack.

The backend will use SQLAlchemy async with `AsyncEngine`, `async_sessionmaker`, and `AsyncSession`. PostgreSQL URLs must use the `postgresql+asyncpg` dialect.

## Consequences

- Application, repository, and unit-of-work code that touches the database must be compatible with `async` and `await`.
- Alembic must be configured to work with the async database URL.
- The project gains a stack aligned with Python, API development, and future AI/RAG/agent integrations.
- The project must use tests, typing, and clear architecture boundaries to keep Python code maintainable as the domain grows.
