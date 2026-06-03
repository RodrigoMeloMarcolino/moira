from typing import Protocol
from uuid import UUID

from app.modules.auth.infrastructure.models import User
from app.modules.providers.infrastructure.models import Provider


class UserRepository(Protocol):
    async def find_id_by_email(self, email: str) -> UUID | None: ...

    async def add(self, user: User) -> None: ...


class ProviderRepository(Protocol):
    async def find_id_by_slug(self, slug: str) -> UUID | None: ...

    async def get_by_id(self, provider_id: UUID) -> Provider | None: ...

    async def get_by_slug(self, slug: str) -> Provider | None: ...

    async def add(self, provider: Provider) -> None: ...
