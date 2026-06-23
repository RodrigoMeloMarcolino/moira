from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.modules.providers.application.public_cache import (
    ProviderCatalogCache,
)
from app.modules.providers.application.use_cases import GetPublicProviderBySlugUseCase
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


def async_cache_mock(*, payload: str | None = None) -> Mock:
    cache = Mock(spec=AsyncCache)
    cache.get = AsyncMock(return_value=payload)
    cache.set = AsyncMock()
    return cache


async def test_provider_catalog_cache_round_trip() -> None:
    payload = (
        f'{{"id": "{uuid4()}", "display_name": "Provider Test", '
        '"slug": "provider-test", "timezone": "America/Fortaleza", '
        '"currency_code": "BRL"}'
    )
    cache = ProviderCatalogCache(async_cache_mock(payload=payload), ttl_seconds=1800)

    provider_catalog = await cache.get('provider-test')

    assert provider_catalog is not None
    assert provider_catalog.slug == 'provider-test'


async def test_get_public_provider_by_slug_use_case_returns_cached_payload() -> None:
    providers = Mock()
    providers.get_by_slug = AsyncMock()
    public_cache = Mock(spec=ProviderCatalogCache)
    public_cache.set = AsyncMock()
    cached_provider = await ProviderCatalogCache(
        async_cache_mock(
            payload=(
                f'{{"id": "{uuid4()}", "display_name": "Provider Test", '
                '"slug": "provider-test", "timezone": "America/Fortaleza", '
                '"currency_code": "BRL"}'
            )
        ),
        ttl_seconds=1800,
    ).get('provider-test')
    public_cache.get = AsyncMock(return_value=cached_provider)
    use_case = GetPublicProviderBySlugUseCase(
        providers=providers,
        public_cache=public_cache,
    )

    public_provider = await use_case.execute('provider-test')

    assert public_provider.slug == 'provider-test'
    providers.get_by_slug.assert_not_awaited()


async def test_get_public_provider_by_slug_use_case_caches_miss() -> None:
    fresh_provider = provider()
    providers = Mock()
    providers.get_by_slug = AsyncMock(return_value=fresh_provider)
    public_cache = Mock(spec=ProviderCatalogCache)
    public_cache.get = AsyncMock(return_value=None)
    public_cache.set = AsyncMock()
    use_case = GetPublicProviderBySlugUseCase(
        providers=providers,
        public_cache=public_cache,
    )

    public_provider = await use_case.execute('provider-test')

    assert public_provider.slug == fresh_provider.slug
    public_cache.set.assert_awaited_once()
