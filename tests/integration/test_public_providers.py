import pytest
from httpx import AsyncClient

from tests.integration.conftest import signup_provider, unique_value

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_get_provider_by_slug_returns_public_provider(
    client: AsyncClient,
) -> None:
    provider = await signup_provider(client)

    response = await client.get(f'/providers/{provider["slug"]}')

    assert response.status_code == 200
    assert response.json() == provider


async def test_get_provider_by_slug_returns_404_for_missing_provider(
    client: AsyncClient,
) -> None:
    response = await client.get(f'/providers/{unique_value("missing")}')

    assert response.status_code == 404
