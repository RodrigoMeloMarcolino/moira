from datetime import timedelta
from typing import Optional
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest

from app.modules.auth.application.exceptions import InvalidCredentials
from app.modules.auth.application.ports import AccessTokenIssuer, PasswordHasher
from app.modules.auth.application.use_cases import LoginProviderUseCase
from app.modules.auth.schemas.login import LoginCreate
from app.modules.providers.application.output_ports import ProviderRepository
from app.modules.providers.infrastructure.models import Provider
from app.modules.users.application.output_ports import UserRepository
from app.modules.users.infrastructure.models import User


def user() -> User:
    return User(
        id=uuid4(),
        email='provider@example.com',
        password_hash='hashed-password',
    )


def provider(user_id) -> Provider:
    return Provider(
        id=uuid4(),
        user_id=user_id,
        display_name='Provider Test',
        slug='provider-test',
        timezone='America/Fortaleza',
        currency_code='BRL',
    )


def build_use_case(
    *,
    existing_user: Optional[User],
    existing_provider: Optional[Provider],
    password_matches: bool = True,
) -> LoginProviderUseCase:
    users = Mock(spec=UserRepository)
    users.get_by_email = AsyncMock(return_value=existing_user)

    providers = Mock(spec=ProviderRepository)
    providers.get_by_user_id = AsyncMock(return_value=existing_provider)

    password_hasher = Mock(spec=PasswordHasher)
    password_hasher.verify = Mock(return_value=password_matches)

    access_tokens = Mock(spec=AccessTokenIssuer)
    access_tokens.issue_access_token = Mock(return_value='access-token')

    return LoginProviderUseCase(
        users=users,
        providers=providers,
        password_hasher=password_hasher,
        access_tokens=access_tokens,
        access_token_expires_in=int(timedelta(minutes=30).total_seconds()),
    )


@pytest.mark.asyncio
async def test_login_provider_returns_access_token_for_valid_credentials() -> None:
    existing_user = user()
    existing_provider = provider(existing_user.id)
    use_case = build_use_case(
        existing_user=existing_user,
        existing_provider=existing_provider,
    )

    result = await use_case.execute(
        LoginCreate(email=existing_user.email, password='secure-password')
    )

    assert result.access_token == 'access-token'
    assert result.token_type == 'bearer'
    assert result.expires_in == 1800
    assert result.provider_id == existing_provider.id


@pytest.mark.asyncio
async def test_login_provider_rejects_missing_user() -> None:
    use_case = build_use_case(existing_user=None, existing_provider=None)

    with pytest.raises(InvalidCredentials):
        await use_case.execute(
            LoginCreate(email='missing@example.com', password='secure-password')
        )


@pytest.mark.asyncio
async def test_login_provider_rejects_invalid_password() -> None:
    existing_user = user()
    use_case = build_use_case(
        existing_user=existing_user,
        existing_provider=provider(existing_user.id),
        password_matches=False,
    )

    with pytest.raises(InvalidCredentials):
        await use_case.execute(
            LoginCreate(email=existing_user.email, password='wrong-password')
        )


@pytest.mark.asyncio
async def test_login_provider_rejects_user_without_provider() -> None:
    existing_user = user()
    use_case = build_use_case(existing_user=existing_user, existing_provider=None)

    with pytest.raises(InvalidCredentials):
        await use_case.execute(
            LoginCreate(email=existing_user.email, password='secure-password')
        )
