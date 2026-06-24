from __future__ import annotations

import json
import logging

from pydantic import ValidationError

from app.modules.providers.schemas.catalog import ProviderCatalogPublic
from app.shared.application.cache import AsyncCache

logger = logging.getLogger(__name__)


class ProviderCatalogCache:
    def __init__(
        self,
        cache: AsyncCache,
        *,
        ttl_seconds: int,
    ) -> None:
        self.cache = cache
        self.ttl_seconds = ttl_seconds

    async def get(self, slug: str) -> ProviderCatalogPublic | None:
        payload = await self.cache.get(self._key(slug))
        if payload is None:
            return None

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            self._log_invalid('invalid_json')
            return None

        if not isinstance(data, dict):
            self._log_invalid('invalid_shape')
            return None

        try:
            return ProviderCatalogPublic.model_validate(data)
        except ValidationError:
            self._log_invalid('invalid_schema')
            return None

    async def set(self, provider: ProviderCatalogPublic) -> None:
        await self.cache.set(
            self._key(provider.slug),
            json.dumps(provider.model_dump(mode='json')),
            ttl_seconds=self.ttl_seconds,
        )

    def _key(self, slug: str) -> str:
        return f'public_provider:{slug}'

    def _log_invalid(self, reason: str) -> None:
        logger.warning(
            'Public provider cache payload is invalid',
            extra={
                'event_name': 'cache.payload_invalid',
                'cache_namespace': 'public_provider',
                'reason': reason,
            },
        )
