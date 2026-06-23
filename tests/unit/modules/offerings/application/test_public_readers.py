from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.modules.offerings.application.public_cache import (
    PublicOfferingsCache,
)
from app.modules.offerings.application.use_cases import (
    ListPublicProviderOfferingsUseCase,
)
from app.modules.offerings.infrastructure.models import Offering
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


def async_cache_mock(*, payload: str | None = None) -> Mock:
    cache = Mock(spec=AsyncCache)
    cache.get = AsyncMock(return_value=payload)
    cache.set = AsyncMock()
    cache.delete = AsyncMock()
    return cache


async def test_public_offerings_cache_round_trip() -> None:
    current_provider = provider()
    cache = PublicOfferingsCache(
        async_cache_mock(
            payload=(
                f'[{{"id": "{uuid4()}", "provider_id": "{current_provider.id}", '
                '"title": "Consulta", '
                '"description": "Atendimento inicial", "duration_minutes": 30, '
                '"price_cents": 15000, "is_active": true}]'
            )
        ),
        ttl_seconds=600,
    )

    public_offerings = await cache.get(current_provider.id)

    assert public_offerings is not None
    assert [offering.title for offering in public_offerings] == ['Consulta']


async def test_list_public_provider_offerings_returns_cached_payload() -> None:
    current_provider = provider()
    offerings = Mock()
    offerings.list_active_by_provider_id = AsyncMock()
    public_cache = Mock(spec=PublicOfferingsCache)
    cached_offerings = await PublicOfferingsCache(
        async_cache_mock(
            payload=(
                f'[{{"id": "{uuid4()}", "provider_id": "{current_provider.id}", '
                '"title": "Consulta", '
                '"description": "Atendimento inicial", "duration_minutes": 30, '
                '"price_cents": 15000, "is_active": true}]'
            )
        ),
        ttl_seconds=600,
    ).get(current_provider.id)
    public_cache.get = AsyncMock(
        return_value=cached_offerings
    )
    public_cache.set = AsyncMock()
    use_case = ListPublicProviderOfferingsUseCase(
        providers=Mock(get_by_slug=AsyncMock(return_value=current_provider)),
        offerings=offerings,
        public_cache=public_cache,
    )

    public_offerings = await use_case.execute(current_provider.slug)

    assert [offering.title for offering in public_offerings] == ['Consulta']
    offerings.list_active_by_provider_id.assert_not_awaited()


async def test_list_public_provider_offerings_caches_miss() -> None:
    current_provider = provider()
    fresh_offering = offering(current_provider.id)
    offerings = Mock()
    offerings.list_active_by_provider_id = AsyncMock(return_value=[fresh_offering])
    public_cache = Mock(spec=PublicOfferingsCache)
    public_cache.get = AsyncMock(return_value=None)
    public_cache.set = AsyncMock()
    use_case = ListPublicProviderOfferingsUseCase(
        providers=Mock(get_by_slug=AsyncMock(return_value=current_provider)),
        offerings=offerings,
        public_cache=public_cache,
    )

    public_offerings = await use_case.execute(current_provider.slug)

    assert [offering.title for offering in public_offerings] == ['Consulta']
    public_cache.set.assert_awaited_once()
