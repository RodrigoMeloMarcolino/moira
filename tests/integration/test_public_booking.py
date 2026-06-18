from uuid import uuid4

import pytest
from httpx import AsyncClient

from tests.integration.conftest import signup_authenticated_provider, unique_value

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


def unique_phone() -> str:
    return f'+1555{uuid4().int % 10_000_000_000:010d}'


async def _create_bookable_provider(client: AsyncClient) -> tuple[dict, dict, dict]:
    provider, headers = await signup_authenticated_provider(client)
    offering_response = await client.post(
        f'/providers/{provider["id"]}/offerings',
        headers=headers,
        json={
            'title': 'Consulta',
            'duration_minutes': 30,
        },
    )
    assert offering_response.status_code == 201

    availability_response = await client.post(
        f'/providers/{provider["id"]}/availability-rules',
        headers=headers,
        json={
            'weekday': 3,
            'start_time': '09:00',
            'end_time': '10:00',
        },
    )
    assert availability_response.status_code == 201

    return provider, headers, offering_response.json()


async def test_public_booking_reuses_same_idempotency_key_payload(
    client: AsyncClient,
) -> None:
    provider, headers, offering = await _create_bookable_provider(client)
    payload = {
        'offering_id': offering['id'],
        'start_at': '2026-06-10T09:00:00',
        'customer_name': 'Customer Test',
        'customer_phone': unique_phone(),
    }
    idempotency_headers = {'Idempotency-Key': unique_value('retry')}

    first_response = await client.post(
        f'/providers/{provider["slug"]}/appointments',
        headers=idempotency_headers,
        json=payload,
    )
    second_response = await client.post(
        f'/providers/{provider["slug"]}/appointments',
        headers=idempotency_headers,
        json=payload,
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 201
    assert second_response.json()['id'] == first_response.json()['id']

    appointments_response = await client.get(
        f'/providers/{provider["id"]}/appointments',
        headers=headers,
    )
    assert appointments_response.status_code == 200
    assert [item['id'] for item in appointments_response.json()] == [
        first_response.json()['id']
    ]


async def test_public_booking_rejects_same_idempotency_key_with_other_payload(
    client: AsyncClient,
) -> None:
    provider, _, offering = await _create_bookable_provider(client)
    idempotency_headers = {'Idempotency-Key': unique_value('retry')}
    payload = {
        'offering_id': offering['id'],
        'start_at': '2026-06-10T09:00:00',
        'customer_name': 'Customer Test',
        'customer_phone': unique_phone(),
    }

    first_response = await client.post(
        f'/providers/{provider["slug"]}/appointments',
        headers=idempotency_headers,
        json=payload,
    )
    second_response = await client.post(
        f'/providers/{provider["slug"]}/appointments',
        headers=idempotency_headers,
        json={**payload, 'customer_name': 'Other Customer'},
    )

    assert first_response.status_code == 201
    assert second_response.status_code == 409
