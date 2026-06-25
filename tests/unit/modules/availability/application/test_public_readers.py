from datetime import UTC, date, datetime
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.modules.availability.application.public_cache import (
    RedisPublicAvailabilityCache,
)
from app.modules.availability.application.use_cases import (
    ListProviderAvailableSlotsUseCase,
    ListPublicProviderAvailableSlotsUseCase,
)
from app.modules.offerings.application.output_ports import OfferingRepository
from app.modules.offerings.infrastructure.models import Offering
from app.modules.providers.application.output_ports import ProviderRepository
from app.modules.providers.infrastructure.models import Provider
from app.shared.application.cache import AsyncCache

pytestmark = pytest.mark.asyncio


def provider() -> Provider:
    return Provider(
        id=uuid4(),
        user_id=uuid4(),
        display_name='Provider Test',
        slug='provider-test',
        timezone='America/Fortaleza',
        currency_code='BRL',
    )


def offering(provider_id) -> Offering:
    return Offering(
        id=uuid4(),
        provider_id=provider_id,
        title='Consulta',
        description='Atendimento inicial',
        duration_minutes=30,
        price_cents=15000,
        is_active=True,
    )


def provider_repository_mock(*, provider_by_slug: Provider) -> Mock:
    providers = Mock(spec=ProviderRepository)
    providers.get_by_slug = AsyncMock(return_value=provider_by_slug)
    return providers


def offering_repository_mock(*, active_offering: Offering) -> Mock:
    offerings = Mock(spec=OfferingRepository)
    offerings.get_active_by_id = AsyncMock(return_value=active_offering)
    return offerings


def async_cache_mock(
    *,
    payload: str | None = None,
    version: int | None = 1,
) -> Mock:
    cache = Mock(spec=AsyncCache)
    cache.get = AsyncMock(return_value=payload)
    cache.set = AsyncMock()
    cache.delete = AsyncMock()
    cache.incr = AsyncMock(return_value=2)
    cache.get_int = AsyncMock(return_value=version)
    return cache


async def test_public_availability_cache_returns_cached_slots() -> None:
    current_provider = provider()
    cache = RedisPublicAvailabilityCache(
        async_cache_mock(payload='["2026-06-10T12:00:00+00:00"]'),
        slots_ttl_seconds=30,
    )

    available_slots = await cache.get_slots(
        current_provider.id,
        uuid4(),
        date(2026, 6, 10),
        1,
        1,
    )

    assert available_slots == [datetime(2026, 6, 10, 12, 0, tzinfo=UTC)]


async def test_list_public_provider_available_slots_returns_cached_slots() -> None:
    current_provider = provider()
    current_offering = offering(current_provider.id)
    public_cache = Mock(spec=RedisPublicAvailabilityCache)
    public_cache.get_schedule_version = AsyncMock(return_value=1)
    public_cache.get_day_version = AsyncMock(return_value=1)
    public_cache.get_slots = AsyncMock(
        return_value=[datetime(2026, 6, 10, 12, 0, tzinfo=UTC)]
    )
    public_cache.set_slots = AsyncMock()
    fresh_use_case = Mock(spec=ListProviderAvailableSlotsUseCase)
    fresh_use_case.execute = AsyncMock()
    use_case = ListPublicProviderAvailableSlotsUseCase(
        providers=provider_repository_mock(provider_by_slug=current_provider),
        offerings=offering_repository_mock(active_offering=current_offering),
        list_provider_available_slots=fresh_use_case,
        public_cache=public_cache,
    )

    available_slots = await use_case.execute(
        current_provider.slug,
        current_offering.id,
        date(2026, 6, 10),
    )

    assert available_slots == [datetime(2026, 6, 10, 12, 0, tzinfo=UTC)]
    fresh_use_case.execute.assert_not_awaited()


async def test_list_public_provider_available_slots_caches_miss() -> None:
    current_provider = provider()
    current_offering = offering(current_provider.id)
    public_cache = Mock(spec=RedisPublicAvailabilityCache)
    public_cache.get_schedule_version = AsyncMock(return_value=1)
    public_cache.get_day_version = AsyncMock(return_value=1)
    public_cache.get_slots = AsyncMock(return_value=None)
    public_cache.set_slots = AsyncMock()
    fresh_slots = [datetime(2026, 6, 10, 12, 0, tzinfo=UTC)]
    fresh_use_case = Mock(spec=ListProviderAvailableSlotsUseCase)
    fresh_use_case.execute = AsyncMock(return_value=fresh_slots)
    use_case = ListPublicProviderAvailableSlotsUseCase(
        providers=provider_repository_mock(provider_by_slug=current_provider),
        offerings=offering_repository_mock(active_offering=current_offering),
        list_provider_available_slots=fresh_use_case,
        public_cache=public_cache,
    )

    available_slots = await use_case.execute(
        current_provider.slug,
        current_offering.id,
        date(2026, 6, 10),
    )

    assert available_slots == fresh_slots
    public_cache.set_slots.assert_awaited_once_with(
        current_provider.id,
        current_offering.id,
        date(2026, 6, 10),
        1,
        1,
        fresh_slots,
    )
