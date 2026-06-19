import pytest
from httpx import AsyncClient

from tests.integration.conftest import signup_provider, unique_value

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_provider_login_returns_access_token(client: AsyncClient) -> None:
    email = f'{unique_value("provider")}@example.com'
    password = 'secure-password'
    provider = await signup_provider(client, email=email, password=password)

    response = await client.post(
        '/v1/auth/login',
        json={
            'email': email,
            'password': password,
        },
    )

    assert response.status_code == 200
    body = response.json()
    assert body['access_token']
    assert body['token_type'] == 'bearer'
    assert body['expires_in'] == 1800
    assert body['provider_id'] == provider['id']


async def test_provider_login_rejects_invalid_credentials(
    client: AsyncClient,
) -> None:
    response = await client.post(
        '/v1/auth/login',
        json={
            'email': 'missing@example.com',
            'password': 'wrong-password',
        },
    )

    assert response.status_code == 401
    assert response.json() == {
        'error': {
            'code': 'invalid_credentials',
            'message': 'invalid credentials',
            'details': None,
        }
    }
