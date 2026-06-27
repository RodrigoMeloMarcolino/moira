from __future__ import annotations

import logging
from typing import Any

from app.config import Settings
from app.shared.application.cache import AsyncCache

redis: Any | None
RedisLibraryError: type[Exception] | None

try:
    import redis.asyncio as redis_module
    from redis.exceptions import RedisError as RedisPackageError
except ImportError:  # pragma: no cover - exercised indirectly in runtime fallback
    redis = None
    RedisLibraryError = None
else:
    redis = redis_module
    RedisLibraryError = RedisPackageError


logger = logging.getLogger(__name__)


def _is_expected_redis_backend_error(exc: Exception) -> bool:
    if isinstance(exc, OSError):
        return True

    return RedisLibraryError is not None and isinstance(exc, RedisLibraryError)


class NullCache:
    async def get(self, key: str) -> str | None:
        return None

    async def set(
        self,
        key: str,
        value: str,
        ttl_seconds: int | None = None,
    ) -> None:
        return None

    async def delete(self, key: str) -> None:
        return None

    async def incr(self, key: str) -> int:
        return 1

    async def get_int(self, key: str) -> int | None:
        return None


class RedisCache:
    def __init__(self, client: Any) -> None:
        self.client = client

    async def get(self, key: str) -> str | None:
        try:
            return await self.client.get(key)
        except Exception as exc:
            if not _is_expected_redis_backend_error(exc):
                raise
            self._log_failure('get', key, exc)
            return None

    async def set(
        self,
        key: str,
        value: str,
        ttl_seconds: int | None = None,
    ) -> None:
        try:
            await self.client.set(key, value, ex=ttl_seconds)
        except Exception as exc:
            if not _is_expected_redis_backend_error(exc):
                raise
            self._log_failure('set', key, exc)

    async def delete(self, key: str) -> None:
        try:
            await self.client.delete(key)
        except Exception as exc:
            if not _is_expected_redis_backend_error(exc):
                raise
            self._log_failure('delete', key, exc)

    async def incr(self, key: str) -> int:
        try:
            return int(await self.client.incr(key))
        except Exception as exc:
            if not _is_expected_redis_backend_error(exc):
                raise
            self._log_failure('incr', key, exc)
            return 1

    async def get_int(self, key: str) -> int | None:
        value = await self.get(key)
        if value is None:
            return None

        try:
            return int(value)
        except ValueError:
            logger.warning(
                'Cache payload is not an integer',
                extra={
                    'event_name': 'cache.payload_invalid',
                    'cache_namespace': key.partition(':')[0],
                    'reason': 'invalid_integer',
                },
            )
            return None

    def _log_failure(self, operation: str, key: str, exc: Exception) -> None:
        logger.warning(
            'Redis cache operation failed',
            extra={
                'event_name': 'cache.backend_degraded',
                'operation': operation,
                'cache_namespace': key.partition(':')[0],
                'reason': type(exc).__name__,
            },
        )


async def build_cache_backend(settings: Settings) -> tuple[AsyncCache, Any | None]:
    if not settings.cache_enabled:
        return NullCache(), None

    if redis is None:
        logger.warning(
            'Redis package is unavailable; falling back to null cache',
            extra={
                'event_name': 'cache.backend_degraded',
                'reason': 'package_unavailable',
            },
        )
        return NullCache(), None

    redis_url = settings.redis_url.get_secret_value()
    client = redis.from_url(redis_url, decode_responses=True)

    try:
        await client.ping()
    except Exception as exc:
        if not _is_expected_redis_backend_error(exc):
            raise

        logger.warning(
            'Redis is unavailable; falling back to null cache',
            extra={
                'event_name': 'cache.backend_degraded',
                'operation': 'ping',
                'reason': type(exc).__name__,
            },
        )
        await client.aclose()
        return NullCache(), None

    logger.info(
        'Redis cache backend is ready',
        extra={'event_name': 'cache.backend_ready', 'backend': 'redis'},
    )
    return RedisCache(client), client
