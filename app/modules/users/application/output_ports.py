from typing import Protocol
from uuid import UUID

from app.modules.users.infrastructure.models import User


class UserRepository(Protocol):
    async def find_id_by_email(self, email: str) -> UUID | None: ...

    async def add(self, user: User) -> None: ...
