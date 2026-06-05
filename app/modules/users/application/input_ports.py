from typing import Protocol

from app.modules.users.infrastructure.models import User


class UserCreator(Protocol):
    async def execute(self, *, email: str, password: str) -> User: ...
