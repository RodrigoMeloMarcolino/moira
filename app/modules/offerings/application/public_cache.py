from __future__ import annotations

import json
from uuid import UUID

from app.modules.offerings.schemas.catalog import OfferingPublic
from app.shared.application.cache import AsyncCache


class PublicOfferingsCache:
    def __init__(
        self,
        cache: AsyncCache,
        *,
        ttl_seconds: int,
    ) -> None:
        self.cache = cache
        self.ttl_seconds = ttl_seconds

    async def get(self, provider_id: UUID) -> list[OfferingPublic] | None:
        payload = await self.cache.get(self._key(provider_id))
        if payload is None:
            return None

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return None

        if not isinstance(data, list):
            return None

        return [
            OfferingPublic.model_validate(item)
            for item in data
            if isinstance(item, dict)
        ]

    async def set(
        self,
        provider_id: UUID,
        offerings: list[OfferingPublic],
    ) -> None:
        await self.cache.set(
            self._key(provider_id),
            json.dumps([offering.model_dump(mode='json') for offering in offerings]),
            ttl_seconds=self.ttl_seconds,
        )

    async def invalidate(self, provider_id: UUID) -> None:
        await self.cache.delete(self._key(provider_id))

    def _key(self, provider_id: UUID) -> str:
        return f'public_offerings:{provider_id}'
