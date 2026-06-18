import pytest
from httpx import AsyncClient

from tests.integration.conftest import unique_value

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_legacy_unversioned_routes_are_not_registered(
    client: AsyncClient,
) -> None:
    response = await client.get('/health')

    assert response.status_code == 404
    assert response.json() == {
        'error': {
            'code': 'not_found',
            'message': 'Not Found',
            'details': None,
        }
    }


async def test_not_found_errors_use_error_envelope(client: AsyncClient) -> None:
    response = await client.get(f'/v1/public/providers/{unique_value("missing")}')

    assert response.status_code == 404
    assert response.json() == {
        'error': {
            'code': 'provider_not_found',
            'message': 'provider not found',
            'details': None,
        }
    }


async def test_validation_errors_use_error_envelope(client: AsyncClient) -> None:
    response = await client.post(
        '/v1/providers/signup',
        json={
            'email': 'provider@example.com',
            'password': 'short',
            'display_name': 'Provider Test',
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body['error']['code'] == 'validation_error'
    assert body['error']['message'] == 'request validation failed'
    assert body['error']['details']
