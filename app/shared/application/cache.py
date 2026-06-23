from typing import Protocol


class AsyncCache(Protocol):
    async def get(self, key: str) -> str | None: ...

    async def set(
        self,
        key: str,
        value: str,
        ttl_seconds: int | None = None,
    ) -> None: ...

    async def delete(self, key: str) -> None: ...

    async def incr(self, key: str) -> int: ...

    async def get_int(self, key: str) -> int | None: ...
