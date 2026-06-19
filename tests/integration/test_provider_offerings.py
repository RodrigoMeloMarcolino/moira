from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.integration.conftest import (
    signup_authenticated_provider,
    signup_provider,
    unique_value,
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_create_offering_with_valid_duration(client: AsyncClient) -> None:
    provider, headers = await signup_authenticated_provider(client)

    response = await client.post(
        f'/v1/providers/{provider["id"]}/offerings',
        headers=headers,
        json={
            'title': 'Consulta',
            'description': 'Atendimento inicial',
            'duration_minutes': 30,
            'price_cents': 15000,
        },
    )

    assert response.status_code == 201
    body = response.json()
    assert body['provider_id'] == provider['id']
    assert body['title'] == 'Consulta'
    assert body['duration_minutes'] == 30
    assert body['price_cents'] == 15000
    assert body['is_active'] is True


async def test_create_offering_requires_authentication(client: AsyncClient) -> None:
    provider = await signup_provider(client)

    response = await client.post(
        f'/v1/providers/{provider["id"]}/offerings',
        json={
            'title': 'Consulta',
            'duration_minutes': 30,
        },
    )

    assert response.status_code == 401


async def test_create_offering_rejects_other_provider_token(
    client: AsyncClient,
) -> None:
    first_provider, first_headers = await signup_authenticated_provider(client)
    other_provider = await signup_provider(client)

    response = await client.post(
        f'/v1/providers/{other_provider["id"]}/offerings',
        headers=first_headers,
        json={
            'title': 'Consulta',
            'duration_minutes': 30,
        },
    )

    assert first_provider['id'] != other_provider['id']
    assert response.status_code == 403


async def test_create_offering_rejects_duration_that_is_not_multiple_of_15(
    client: AsyncClient,
) -> None:
    provider, headers = await signup_authenticated_provider(client)

    response = await client.post(
        f'/v1/providers/{provider["id"]}/offerings',
        headers=headers,
        json={
            'title': 'Consulta',
            'duration_minutes': 20,
        },
    )

    assert response.status_code == 422


async def test_create_offering_rejects_negative_price(client: AsyncClient) -> None:
    provider, headers = await signup_authenticated_provider(client)

    response = await client.post(
        f'/v1/providers/{provider["id"]}/offerings',
        headers=headers,
        json={
            'title': 'Consulta',
            'duration_minutes': 30,
            'price_cents': -1,
        },
    )

    assert response.status_code == 422


async def test_list_provider_offerings_returns_only_active_offerings(
    client: AsyncClient,
) -> None:
    provider, headers = await signup_authenticated_provider(client)

    active_response = await client.post(
        f'/v1/providers/{provider["id"]}/offerings',
        headers=headers,
        json={
            'title': 'Ativa',
            'duration_minutes': 30,
            'is_active': True,
        },
    )
    assert active_response.status_code == 201

    inactive_response = await client.post(
        f'/v1/providers/{provider["id"]}/offerings',
        headers=headers,
        json={
            'title': 'Inativa',
            'duration_minutes': 30,
            'is_active': False,
        },
    )
    assert inactive_response.status_code == 201

    response = await client.get(f'/v1/public/providers/{provider["slug"]}/offerings')

    assert response.status_code == 200
    offerings = response.json()
    assert [offering['title'] for offering in offerings] == ['Ativa']

    admin_response = await client.get(
        f'/v1/providers/{provider["id"]}/offerings',
        headers=headers,
    )
    assert admin_response.status_code == 200
    assert [offering['title'] for offering in admin_response.json()] == [
        'Ativa',
        'Inativa',
    ]


async def test_patch_offering_can_deactivate_offering(client: AsyncClient) -> None:
    provider, headers = await signup_authenticated_provider(client)

    create_response = await client.post(
        f'/v1/providers/{provider["id"]}/offerings',
        headers=headers,
        json={
            'title': 'Consulta',
            'duration_minutes': 30,
        },
    )
    assert create_response.status_code == 201
    offering = create_response.json()

    response = await client.patch(
        f'/v1/offerings/{offering["id"]}',
        headers=headers,
        json={'is_active': False},
    )

    assert response.status_code == 200
    assert response.json()['is_active'] is False

    list_response = await client.get(
        f'/v1/public/providers/{provider["slug"]}/offerings'
    )
    assert list_response.status_code == 200
    assert list_response.json() == []


async def test_create_offering_returns_404_for_missing_provider(
    client: AsyncClient,
) -> None:
    missing_provider_id = uuid4()
    _, headers = await signup_authenticated_provider(client)

    response = await client.post(
        f'/v1/providers/{missing_provider_id}/offerings',
        headers=headers,
        json={
            'title': 'Consulta',
            'duration_minutes': 30,
        },
    )

    assert response.status_code == 404


async def test_list_provider_offerings_returns_404_for_missing_provider(
    client: AsyncClient,
) -> None:
    response = await client.get(
        f'/v1/public/providers/{unique_value("missing")}/offerings'
    )

    assert response.status_code == 404
