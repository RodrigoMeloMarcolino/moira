from uuid import UUID, uuid4

import pytest

from app.modules.users.application.exceptions import UserEmailAlreadyExists
from app.modules.users.application.use_cases import CreateUserUseCase
from app.modules.users.infrastructure.models import User


class FakeUserRepository:
    def __init__(self, existing_email_id: UUID | None = None) -> None:
        self.existing_email_id = existing_email_id
        self.added: list[User] = []

    async def find_id_by_email(self, email: str) -> UUID | None:
        _ = email
        return self.existing_email_id

    async def add(self, user: User) -> None:
        user.id = uuid4()
        self.added.append(user)


class FakePasswordHasher:
    def __init__(self) -> None:
        self.hashed_passwords: list[str] = []

    def hash(self, password: str) -> str:
        self.hashed_passwords.append(password)
        return f"hashed:{password}"

    def verify(self, password: str, password_hash: str) -> bool:
        return password_hash == f"hashed:{password}"


@pytest.mark.asyncio
async def test_create_user_hashes_password_and_persists_user() -> None:
    users = FakeUserRepository()
    hasher = FakePasswordHasher()
    use_case = CreateUserUseCase(users=users, password_hasher=hasher)

    user = await use_case.execute(
        email="provider@example.com",
        password="secure-password",
    )

    assert users.added == [user]
    assert hasher.hashed_passwords == ["secure-password"]
    assert user.email == "provider@example.com"
    assert user.password_hash == "hashed:secure-password"
    assert user.password_hash != "secure-password"


@pytest.mark.asyncio
async def test_create_user_rejects_duplicate_email_before_hashing() -> None:
    users = FakeUserRepository(existing_email_id=uuid4())
    hasher = FakePasswordHasher()
    use_case = CreateUserUseCase(users=users, password_hasher=hasher)

    with pytest.raises(UserEmailAlreadyExists):
        await use_case.execute(
            email="provider@example.com",
            password="secure-password",
        )

    assert users.added == []
    assert hasher.hashed_passwords == []
