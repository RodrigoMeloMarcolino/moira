from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.modules.auth.application.ports import PasswordHasher
from app.modules.users.application.exceptions import UserEmailAlreadyExists
from app.modules.users.application.output_ports import UserRepository
from app.modules.users.application.use_cases import CreateUserUseCase


@pytest.mark.asyncio
async def test_create_user_hashes_password_and_persists_user() -> None:
    users = Mock(spec=UserRepository)
    users.find_id_by_email = AsyncMock(return_value=None)
    users.add = AsyncMock()
    hasher = Mock(spec=PasswordHasher)
    hasher.hash.return_value = "hashed:secure-password"
    use_case = CreateUserUseCase(users=users, password_hasher=hasher)

    user = await use_case.execute(
        email="provider@example.com",
        password="secure-password",
    )

    users.find_id_by_email.assert_awaited_once_with("provider@example.com")
    hasher.hash.assert_called_once_with("secure-password")
    users.add.assert_awaited_once_with(user)
    assert user.email == "provider@example.com"
    assert user.password_hash == "hashed:secure-password"
    assert user.password_hash != "secure-password"


@pytest.mark.asyncio
async def test_create_user_rejects_duplicate_email_before_hashing() -> None:
    users = Mock(spec=UserRepository)
    users.find_id_by_email = AsyncMock(return_value=uuid4())
    users.add = AsyncMock()
    hasher = Mock(spec=PasswordHasher)
    use_case = CreateUserUseCase(users=users, password_hasher=hasher)

    with pytest.raises(UserEmailAlreadyExists):
        await use_case.execute(
            email="provider@example.com",
            password="secure-password",
        )

    users.find_id_by_email.assert_awaited_once_with("provider@example.com")
    hasher.hash.assert_not_called()
    users.add.assert_not_awaited()
