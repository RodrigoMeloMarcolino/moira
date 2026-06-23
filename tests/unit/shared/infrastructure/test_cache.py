from unittest.mock import AsyncMock

import pytest

from app.shared.infrastructure.cache import RedisCache

pytestmark = pytest.mark.asyncio


async def test_redis_cache_returns_safe_defaults_when_backend_fails() -> None:
    client = AsyncMock()
    client.get.side_effect = RuntimeError('boom')
    client.set.side_effect = RuntimeError('boom')
    client.delete.side_effect = RuntimeError('boom')
    client.incr.side_effect = RuntimeError('boom')
    cache = RedisCache(client)

    assert await cache.get('key') is None
    assert await cache.get_int('key') is None
    assert await cache.incr('key') == 1
    await cache.set('key', 'value', ttl_seconds=30)
    await cache.delete('key')
