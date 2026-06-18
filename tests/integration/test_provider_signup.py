import pytest
from httpx import AsyncClient
from sqlalchemy import select

from app.modules.auth.infrastructure.passwords import BcryptPasswordHasher
from app.modules.users.infrastructure.models import User
from tests.integration.conftest import unique_value

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_signup_provider_creates_user_and_provider(
    client: AsyncClient,
) -> None:
    email_slug = unique_value('provider')
    password = 'secure-password'

    response = await client.post(
        '/v1/providers/signup',
        json={
            'email': f'{email_slug}@example.com',
            'password': password,
            'display_name': 'Provider Test',
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body['id']
    assert body['user_id']
    assert body['display_name'] == 'Provider Test'
    assert body['slug'].startswith('provider-test-')
    assert len(body['slug']) <= 80
    assert body['timezone'] == 'America/Fortaleza'
    assert body['currency_code'] == 'BRL'
    assert 'password' not in body
    assert 'password_hash' not in body

    from app.database import async_session_factory

    async with async_session_factory() as session:
        password_hash = await session.scalar(
            select(User.password_hash).where(User.id == body['user_id'])
        )

    assert password_hash is not None
    assert password_hash != password
    assert BcryptPasswordHasher().verify(password, password_hash)


@pytest.mark.parametrize('password', ['a' * 8, 'a' * 64])
async def test_signup_provider_accepts_functional_password_boundaries(
    client: AsyncClient,
    password: str,
) -> None:
    email_slug = unique_value('provider')

    response = await client.post(
        '/v1/providers/signup',
        json={
            'email': f'{email_slug}@example.com',
            'password': password,
            'display_name': 'Provider Test',
        },
    )

    assert response.status_code == 201


@pytest.mark.parametrize('password', ['a' * 7, 'a' * 65])
async def test_signup_provider_rejects_invalid_functional_password_lengths(
    client: AsyncClient,
    password: str,
) -> None:
    email_slug = unique_value('provider')

    response = await client.post(
        '/v1/providers/signup',
        json={
            'email': f'{email_slug}@example.com',
            'password': password,
            'display_name': 'Provider Test',
        },
    )

    assert response.status_code == 422


async def test_signup_provider_rejects_duplicate_email(
    client: AsyncClient,
) -> None:
    email_slug = unique_value('provider')
    email = f'{email_slug}@example.com'

    first_response = await client.post(
        '/v1/providers/signup',
        json={
            'email': email,
            'password': 'secure-password',
            'display_name': 'Provider Test',
        },
    )
    assert first_response.status_code == 201

    response = await client.post(
        '/v1/providers/signup',
        json={
            'email': email,
            'password': 'secure-password',
            'display_name': 'Other Provider',
        },
    )

    assert response.status_code == 409


async def test_signup_provider_generates_distinct_slugs_for_same_display_name(
    client: AsyncClient,
) -> None:
    first_response = await client.post(
        '/v1/providers/signup',
        json={
            'email': f'{unique_value("provider")}@example.com',
            'password': 'secure-password',
            'display_name': 'Provider Test',
        },
    )
    assert first_response.status_code == 201
    first_body = first_response.json()

    response = await client.post(
        '/v1/providers/signup',
        json={
            'email': f'{unique_value("provider")}@example.com',
            'password': 'secure-password',
            'display_name': 'Provider Test',
        },
    )

    assert response.status_code == 201
    second_body = response.json()
    assert first_body['slug'] != second_body['slug']
    assert first_body['slug'].startswith('provider-test-')
    assert second_body['slug'].startswith('provider-test-')


async def test_signup_provider_rejects_slug_in_body(client: AsyncClient) -> None:
    response = await client.post(
        '/v1/providers/signup',
        json={
            'email': f'{unique_value("provider")}@example.com',
            'password': 'secure-password',
            'display_name': 'Provider Test',
            'slug': 'provider-test-a1b2c3d4',
        },
    )

    assert response.status_code == 422
