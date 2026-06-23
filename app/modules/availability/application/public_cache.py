from __future__ import annotations

import json
from datetime import date, datetime
from typing import Protocol
from uuid import UUID

from app.shared.application.cache import AsyncCache


class PublicAvailabilityCache(Protocol):
    async def get_schedule_version(self, provider_id: UUID) -> int: ...

    async def bump_schedule_version(self, provider_id: UUID) -> int: ...

    async def get_day_version(self, provider_id: UUID, target_date: date) -> int: ...

    async def bump_day_version(self, provider_id: UUID, target_date: date) -> int: ...

    async def get_slots(
        self,
        provider_id: UUID,
        offering_id: UUID,
        target_date: date,
        schedule_version: int,
        day_version: int,
    ) -> list[datetime] | None: ...

    async def set_slots(
        self,
        provider_id: UUID,
        offering_id: UUID,
        target_date: date,
        schedule_version: int,
        day_version: int,
        slots: list[datetime],
    ) -> None: ...

    async def invalidate_slots(
        self,
        provider_id: UUID,
        offering_id: UUID,
        target_date: date,
    ) -> None: ...


class RedisPublicAvailabilityCache:
    def __init__(
        self,
        cache: AsyncCache,
        *,
        slots_ttl_seconds: int,
    ) -> None:
        self.cache = cache
        self.slots_ttl_seconds = slots_ttl_seconds

    async def get_schedule_version(self, provider_id: UUID) -> int:
        return await self._get_version(self._schedule_version_key(provider_id))

    async def bump_schedule_version(self, provider_id: UUID) -> int:
        return await self._bump_version(self._schedule_version_key(provider_id))

    async def get_day_version(self, provider_id: UUID, target_date: date) -> int:
        return await self._get_version(self._day_version_key(provider_id, target_date))

    async def bump_day_version(self, provider_id: UUID, target_date: date) -> int:
        return await self._bump_version(self._day_version_key(provider_id, target_date))

    async def get_slots(
        self,
        provider_id: UUID,
        offering_id: UUID,
        target_date: date,
        schedule_version: int,
        day_version: int,
    ) -> list[datetime] | None:
        payload = await self.cache.get(
            self._slots_key(
                provider_id,
                offering_id,
                target_date,
                schedule_version,
                day_version,
            )
        )
        if payload is None:
            return None

        try:
            data = json.loads(payload)
        except json.JSONDecodeError:
            return None

        if not isinstance(data, list):
            return None

        return [
            datetime.fromisoformat(item) for item in data if isinstance(item, str)
        ]

    async def set_slots(
        self,
        provider_id: UUID,
        offering_id: UUID,
        target_date: date,
        schedule_version: int,
        day_version: int,
        slots: list[datetime],
    ) -> None:
        await self.cache.set(
            self._slots_key(
                provider_id,
                offering_id,
                target_date,
                schedule_version,
                day_version,
            ),
            json.dumps([slot.isoformat() for slot in slots]),
            ttl_seconds=self.slots_ttl_seconds,
        )

    async def invalidate_slots(
        self,
        provider_id: UUID,
        offering_id: UUID,
        target_date: date,
    ) -> None:
        schedule_version = await self.get_schedule_version(provider_id)
        day_version = await self.get_day_version(provider_id, target_date)
        await self.cache.delete(
            self._slots_key(
                provider_id,
                offering_id,
                target_date,
                schedule_version,
                day_version,
            )
        )

    async def _get_version(self, key: str) -> int:
        current = await self.cache.get_int(key)
        if current is not None and current >= 1:
            return current

        await self.cache.set(key, '1')
        return 1

    async def _bump_version(self, key: str) -> int:
        current = await self.cache.get_int(key)
        if current is None:
            await self.cache.set(key, '2')
            return 2

        return await self.cache.incr(key)

    def _schedule_version_key(self, provider_id: UUID) -> str:
        return f'provider_schedule_version:{provider_id}'

    def _day_version_key(self, provider_id: UUID, target_date: date) -> str:
        return f'provider_day_version:{provider_id}:{target_date.isoformat()}'

    def _slots_key(
        self,
        provider_id: UUID,
        offering_id: UUID,
        target_date: date,
        schedule_version: int,
        day_version: int,
    ) -> str:
        return (
            'available_slots:'
            f'{provider_id}:{offering_id}:{target_date.isoformat()}'
            f':sv{schedule_version}:dv{day_version}'
        )
