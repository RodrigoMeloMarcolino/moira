from __future__ import annotations

import json

from app.modules.providers.schemas.catalog import ProviderCatalogPublic
from app.shared.application.cache import AsyncCache


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
            return None

        if not isinstance(data, dict):
            return None

        return ProviderCatalogPublic.model_validate(data)

    async def set(self, provider: ProviderCatalogPublic) -> None:
        await self.cache.set(
            self._key(provider.slug),
            json.dumps(provider.model_dump(mode='json')),
            ttl_seconds=self.ttl_seconds,
        )

    def _key(self, slug: str) -> str:
        return f'public_provider:{slug}'
