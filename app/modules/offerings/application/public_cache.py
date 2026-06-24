from __future__ import annotations

import json
import logging
from uuid import UUID

from pydantic import ValidationError

from app.modules.offerings.schemas.catalog import OfferingPublic
from app.shared.application.cache import AsyncCache

logger = logging.getLogger(__name__)


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
            self._log_invalid('invalid_json')
            return None

        if not isinstance(data, list):
            self._log_invalid('invalid_shape')
            return None

        if not all(isinstance(item, dict) for item in data):
            self._log_invalid('invalid_shape')
            return None

        try:
            return [OfferingPublic.model_validate(item) for item in data]
        except ValidationError:
            self._log_invalid('invalid_schema')
            return None

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

    def _log_invalid(self, reason: str) -> None:
        logger.warning(
            'Public offerings cache payload is invalid',
            extra={
                'event_name': 'cache.payload_invalid',
                'cache_namespace': 'public_offerings',
                'reason': reason,
            },
        )
