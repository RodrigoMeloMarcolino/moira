from typing import Optional, Protocol
from uuid import UUID

from app.modules.users.infrastructure.models import User


class UserRepository(Protocol):
    async def find_id_by_email(self, email: str) -> Optional[UUID]: ...

    async def get_by_id(self, user_id: UUID) -> Optional[User]: ...

    async def get_by_email(self, email: str) -> Optional[User]: ...

    async def add(self, user: User) -> None: ...
