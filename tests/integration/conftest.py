import os
import sys
from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient


def _runs_integration_tests(config: pytest.Config) -> bool:
    mark_expression = config.option.markexpr.strip()
    return "not integration" not in mark_expression


def pytest_configure(config: pytest.Config) -> None:
    if not _runs_integration_tests(config):
        return

    database_url = os.environ.get("DATABASE_URL", "")
    app_env = os.environ.get("APP_ENV", "")
    allow_integration_database = os.environ.get("MOIRA_ALLOW_INTEGRATION_DATABASE", "")

    if app_env != "test" or allow_integration_database != "1" or not database_url:
        raise pytest.UsageError(
            "Integration tests must be run through `make test-integration` "
            "or `uv run python scripts/run_integration_tests.py`, so pytest uses "
            "the ephemeral PostgreSQL test container."
        )

    if "/moira_test" not in database_url:
        raise pytest.UsageError(
            "Refusing to run integration tests against a database that is not "
            "the ephemeral `moira_test` database."
        )

    forbidden_dev_databases = (
        "localhost:5432/moira",
        "127.0.0.1:5432/moira",
    )
    if any(database in database_url for database in forbidden_dev_databases):
        raise pytest.UsageError(
            "Refusing to run integration tests against the local development "
            "database. Use `make test-integration` instead."
        )


@pytest_asyncio.fixture(autouse=True)
async def dispose_engine_after_test() -> AsyncIterator[None]:
    yield

    if "app.database" not in sys.modules:
        return

    from app.database import engine

    await engine.dispose()


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    from app.main import create_app

    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client


def unique_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


async def signup_provider(client: AsyncClient) -> dict:
    display_name = "Provider Test"
    email_slug = unique_value("provider")
    response = await client.post(
        "/providers/signup",
        json={
            "email": f"{email_slug}@example.com",
            "password": "secure-password",
            "display_name": display_name,
        },
    )

    assert response.status_code == 201
    return response.json()
