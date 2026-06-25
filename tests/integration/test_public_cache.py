import json

import pytest
from httpx import AsyncClient

from tests.integration.conftest import signup_authenticated_provider

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def create_provider_with_catalog(
    client: AsyncClient,
) -> tuple[dict, dict, dict, dict]:
    provider, headers = await signup_authenticated_provider(client)
    offering_response = await client.post(
        '/v1/offerings',
        headers=headers,
        json={
            'title': 'Consulta',
            'duration_minutes': 30,
            'is_active': True,
        },
    )
    assert offering_response.status_code == 201

    availability_response = await client.post(
        '/v1/availability-rules',
        headers=headers,
        json={
            'weekday': 3,
            'start_time': '09:00',
            'end_time': '10:00',
        },
    )
    assert availability_response.status_code == 201

    return provider, headers, offering_response.json(), availability_response.json()


async def test_public_provider_endpoint_populates_cache(
    client: AsyncClient,
    redis_client,
) -> None:
    provider, _ = await signup_authenticated_provider(client)

    response = await client.get(f'/v1/public/providers/{provider["slug"]}')

    assert response.status_code == 200
    cached_provider = await redis_client.get(f'public_provider:{provider["slug"]}')
    assert cached_provider is not None
    assert json.loads(cached_provider)['slug'] == provider['slug']


async def test_public_offerings_cache_is_invalidated_after_patch(
    client: AsyncClient,
    redis_client,
) -> None:
    provider, headers, offering, _ = await create_provider_with_catalog(client)
    offerings_key = f'public_offerings:{provider["id"]}'

    first_response = await client.get(
        f'/v1/public/providers/{provider["slug"]}/offerings'
    )
    assert first_response.status_code == 200
    assert await redis_client.exists(offerings_key) == 1

    patch_response = await client.patch(
        f'/v1/offerings/{offering["id"]}',
        headers=headers,
        json={'is_active': False},
    )

    assert patch_response.status_code == 200
    assert await redis_client.exists(offerings_key) == 0

    second_response = await client.get(
        f'/v1/public/providers/{provider["slug"]}/offerings'
    )
    assert second_response.status_code == 200
    assert second_response.json() == []


async def test_available_slots_cache_uses_versioning_after_rule_update(
    client: AsyncClient,
    redis_client,
) -> None:
    provider, headers, offering, availability_rule = await create_provider_with_catalog(
        client
    )
    slots_response = await client.get(
        f'/v1/public/providers/{provider["slug"]}/available-slots',
        params={
            'offering_id': offering['id'],
            'date': '2026-07-01',
        },
    )

    assert slots_response.status_code == 200
    assert slots_response.json() == [
        '2026-07-01T12:00:00Z',
        '2026-07-01T12:15:00Z',
        '2026-07-01T12:30:00Z',
    ]
    assert await redis_client.get(f'provider_schedule_version:{provider["id"]}') == '2'
    assert (
        await redis_client.get(f'provider_day_version:{provider["id"]}:2026-07-01')
        == '1'
    )
    assert (
        await redis_client.exists(
            f'available_slots:{provider["id"]}:{offering["id"]}:2026-07-01:sv2:dv1'
        )
        == 1
    )

    patch_response = await client.patch(
        f'/v1/availability-rules/{availability_rule["id"]}',
        headers=headers,
        json={'end_time': '09:30'},
    )

    assert patch_response.status_code == 200
    assert await redis_client.get(f'provider_schedule_version:{provider["id"]}') == '3'

    updated_response = await client.get(
        f'/v1/public/providers/{provider["slug"]}/available-slots',
        params={
            'offering_id': offering['id'],
            'date': '2026-07-01',
        },
    )
    assert updated_response.status_code == 200
    assert updated_response.json() == ['2026-07-01T12:00:00Z']
    assert (
        await redis_client.exists(
            f'available_slots:{provider["id"]}:{offering["id"]}:2026-07-01:sv3:dv1'
        )
        == 1
    )


async def test_booking_invalidates_available_slots_for_the_day(
    client: AsyncClient,
    redis_client,
) -> None:
    provider, _, offering, _ = await create_provider_with_catalog(client)
    cache_key = f'available_slots:{provider["id"]}:{offering["id"]}:2026-07-01:sv2:dv1'

    first_response = await client.get(
        f'/v1/public/providers/{provider["slug"]}/available-slots',
        params={
            'offering_id': offering['id'],
            'date': '2026-07-01',
        },
    )
    assert first_response.status_code == 200
    assert await redis_client.exists(cache_key) == 1

    booking_response = await client.post(
        f'/v1/public/providers/{provider["slug"]}/appointments',
        json={
            'offering_id': offering['id'],
            'start_at': '2026-07-01T09:00:00-03:00',
            'customer_name': 'Customer Test',
            'customer_phone': '+155500000000',
        },
    )

    assert booking_response.status_code == 201
    assert await redis_client.exists(cache_key) == 0
    assert (
        await redis_client.get(f'provider_day_version:{provider["id"]}:2026-07-01')
        == '2'
    )

    second_response = await client.get(
        f'/v1/public/providers/{provider["slug"]}/available-slots',
        params={
            'offering_id': offering['id'],
            'date': '2026-07-01',
        },
    )
    assert second_response.status_code == 200
    assert second_response.json() == [
        '2026-07-01T12:30:00Z',
    ]
