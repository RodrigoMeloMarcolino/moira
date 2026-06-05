from collections.abc import AsyncIterator
from uuid import uuid4

import pytest
import pytest_asyncio
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.database import async_session_factory, engine
from app.main import create_app
from app.modules.auth.infrastructure.passwords import BcryptPasswordHasher
from app.modules.users.infrastructure.models import User

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


@pytest_asyncio.fixture
async def client() -> AsyncIterator[AsyncClient]:
    transport = ASGITransport(app=create_app())
    async with AsyncClient(transport=transport, base_url="http://testserver") as client:
        yield client

    await engine.dispose()


def unique_value(prefix: str) -> str:
    return f"{prefix}-{uuid4().hex}"


async def signup_provider(client: AsyncClient) -> dict:
    slug = unique_value("provider")
    response = await client.post(
        "/providers/signup",
        json={
            "email": f"{slug}@example.com",
            "password": "secure-password",
            "display_name": "Provider Test",
            "slug": slug,
        },
    )

    assert response.status_code == 201
    return response.json()


async def test_signup_provider_creates_user_and_provider(
    client: AsyncClient,
) -> None:
    slug = unique_value("provider")
    password = "secure-password"

    response = await client.post(
        "/providers/signup",
        json={
            "email": f"{slug}@example.com",
            "password": password,
            "display_name": "Provider Test",
            "slug": slug,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["id"]
    assert body["user_id"]
    assert body["display_name"] == "Provider Test"
    assert body["slug"] == slug
    assert body["timezone"] == "America/Fortaleza"
    assert body["currency_code"] == "BRL"
    assert "password" not in body
    assert "password_hash" not in body

    async with async_session_factory() as session:
        password_hash = await session.scalar(
            select(User.password_hash).where(User.id == body["user_id"])
        )

    assert password_hash is not None
    assert password_hash != password
    assert BcryptPasswordHasher().verify(password, password_hash)


@pytest.mark.parametrize("password", ["a" * 8, "a" * 64])
async def test_signup_provider_accepts_functional_password_boundaries(
    client: AsyncClient,
    password: str,
) -> None:
    slug = unique_value("provider")

    response = await client.post(
        "/providers/signup",
        json={
            "email": f"{slug}@example.com",
            "password": password,
            "display_name": "Provider Test",
            "slug": slug,
        },
    )

    assert response.status_code == 201


@pytest.mark.parametrize("password", ["a" * 7, "a" * 65])
async def test_signup_provider_rejects_invalid_functional_password_lengths(
    client: AsyncClient,
    password: str,
) -> None:
    slug = unique_value("provider")

    response = await client.post(
        "/providers/signup",
        json={
            "email": f"{slug}@example.com",
            "password": password,
            "display_name": "Provider Test",
            "slug": slug,
        },
    )

    assert response.status_code == 422


async def test_signup_provider_rejects_duplicate_email(
    client: AsyncClient,
) -> None:
    slug = unique_value("provider")
    email = f"{slug}@example.com"

    first_response = await client.post(
        "/providers/signup",
        json={
            "email": email,
            "password": "secure-password",
            "display_name": "Provider Test",
            "slug": slug,
        },
    )
    assert first_response.status_code == 201

    response = await client.post(
        "/providers/signup",
        json={
            "email": email,
            "password": "secure-password",
            "display_name": "Other Provider",
            "slug": unique_value("provider"),
        },
    )

    assert response.status_code == 409


async def test_signup_provider_rejects_duplicate_slug(
    client: AsyncClient,
) -> None:
    slug = unique_value("provider")

    first_response = await client.post(
        "/providers/signup",
        json={
            "email": f"{slug}@example.com",
            "password": "secure-password",
            "display_name": "Provider Test",
            "slug": slug,
        },
    )
    assert first_response.status_code == 201

    response = await client.post(
        "/providers/signup",
        json={
            "email": f"{unique_value('provider')}@example.com",
            "password": "secure-password",
            "display_name": "Other Provider",
            "slug": slug,
        },
    )

    assert response.status_code == 409


async def test_get_provider_by_slug_returns_public_provider(
    client: AsyncClient,
) -> None:
    provider = await signup_provider(client)

    response = await client.get(f"/providers/{provider['slug']}")

    assert response.status_code == 200
    assert response.json() == provider


async def test_create_offering_with_valid_duration(client: AsyncClient) -> None:
    provider = await signup_provider(client)

    response = await client.post(
        f"/providers/{provider['id']}/offerings",
        json={
            "title": "Consulta",
            "description": "Atendimento inicial",
            "duration_minutes": 30,
            "price_cents": 15000,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body["provider_id"] == provider["id"]
    assert body["title"] == "Consulta"
    assert body["duration_minutes"] == 30
    assert body["price_cents"] == 15000
    assert body["is_active"] is True


async def test_create_offering_rejects_duration_that_is_not_multiple_of_15(
    client: AsyncClient,
) -> None:
    provider = await signup_provider(client)

    response = await client.post(
        f"/providers/{provider['id']}/offerings",
        json={
            "title": "Consulta",
            "duration_minutes": 20,
        },
    )

    assert response.status_code == 422


async def test_create_offering_rejects_negative_price(client: AsyncClient) -> None:
    provider = await signup_provider(client)

    response = await client.post(
        f"/providers/{provider['id']}/offerings",
        json={
            "title": "Consulta",
            "duration_minutes": 30,
            "price_cents": -1,
        },
    )

    assert response.status_code == 422


async def test_list_provider_offerings_returns_only_active_offerings(
    client: AsyncClient,
) -> None:
    provider = await signup_provider(client)

    active_response = await client.post(
        f"/providers/{provider['id']}/offerings",
        json={
            "title": "Ativa",
            "duration_minutes": 30,
            "is_active": True,
        },
    )
    assert active_response.status_code == 201

    inactive_response = await client.post(
        f"/providers/{provider['id']}/offerings",
        json={
            "title": "Inativa",
            "duration_minutes": 30,
            "is_active": False,
        },
    )
    assert inactive_response.status_code == 201

    response = await client.get(f"/providers/{provider['slug']}/offerings")

    assert response.status_code == 200
    offerings = response.json()
    assert [offering["title"] for offering in offerings] == ["Ativa"]


async def test_patch_offering_can_deactivate_offering(client: AsyncClient) -> None:
    provider = await signup_provider(client)

    create_response = await client.post(
        f"/providers/{provider['id']}/offerings",
        json={
            "title": "Consulta",
            "duration_minutes": 30,
        },
    )
    assert create_response.status_code == 201
    offering = create_response.json()

    response = await client.patch(
        f"/offerings/{offering['id']}",
        json={"is_active": False},
    )

    assert response.status_code == 200
    assert response.json()["is_active"] is False

    list_response = await client.get(f"/providers/{provider['slug']}/offerings")
    assert list_response.status_code == 200
    assert list_response.json() == []


async def test_provider_not_found_returns_404_for_catalog_operations(
    client: AsyncClient,
) -> None:
    missing_provider_id = uuid4()

    create_response = await client.post(
        f"/providers/{missing_provider_id}/offerings",
        json={
            "title": "Consulta",
            "duration_minutes": 30,
        },
    )
    list_response = await client.get(f"/providers/{unique_value('missing')}/offerings")
    get_response = await client.get(f"/providers/{unique_value('missing')}")

    assert create_response.status_code == 404
    assert list_response.status_code == 404
    assert get_response.status_code == 404
