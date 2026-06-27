from unittest.mock import AsyncMock

import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.config import Settings
from app.shared.infrastructure import cache as cache_module
from app.shared.infrastructure.cache import RedisCache

pytestmark = pytest.mark.asyncio


async def test_redis_cache_returns_safe_defaults_when_expected_backend_fails() -> None:
    client = AsyncMock()
    client.get.side_effect = RedisConnectionError('boom')
    client.set.side_effect = RedisConnectionError('boom')
    client.delete.side_effect = RedisConnectionError('boom')
    client.incr.side_effect = RedisConnectionError('boom')
    cache = RedisCache(client)

    assert await cache.get('key') is None
    assert await cache.get_int('key') is None
    assert await cache.incr('key') == 1
    await cache.set('key', 'value', ttl_seconds=30)
    await cache.delete('key')


async def test_redis_cache_propagates_programmer_errors() -> None:
    client = AsyncMock()
    client.get.side_effect = RuntimeError('bug')
    cache = RedisCache(client)

    with pytest.raises(RuntimeError, match='bug'):
        await cache.get('key')


async def test_build_cache_backend_reads_secret_redis_url(monkeypatch) -> None:
    client = AsyncMock()
    captured: dict[str, object] = {}

    class FakeRedisModule:
        @staticmethod
        def from_url(url: str, *, decode_responses: bool) -> AsyncMock:
            captured['url'] = url
            captured['decode_responses'] = decode_responses
            return client

    monkeypatch.setattr(cache_module, 'redis', FakeRedisModule)

    settings = Settings.model_validate(
        {'REDIS_URL': 'redis://:secret@localhost:6379/0'}
    )

    backend, redis_client = await cache_module.build_cache_backend(settings)

    assert isinstance(backend, RedisCache)
    assert redis_client is client
    assert captured == {
        'url': 'redis://:secret@localhost:6379/0',
        'decode_responses': True,
    }
