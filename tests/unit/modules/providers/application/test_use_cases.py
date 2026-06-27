import logging
from typing import Optional
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest

from app.modules.auth.domain.password_policy import SignupPasswordPolicyError
from app.modules.providers.application import use_cases as provider_use_cases
from app.modules.providers.application.exceptions import (
    ProviderEmailAlreadyExists,
    ProviderNotFound,
    ProviderSignupConflict,
)
from app.modules.providers.application.output_ports import ProviderRepository
from app.modules.providers.application.use_cases import (
    GetProviderBySlugUseCase,
    SignupProviderUseCase,
)
from app.modules.providers.infrastructure.models import Provider
from app.modules.providers.schemas.catalog import ProviderSignupCreate
from app.modules.users.application.exceptions import UserEmailAlreadyExists
from app.modules.users.application.input_ports import UserCreator
from app.modules.users.infrastructure.models import User
from app.shared.application.exceptions import UnitOfWorkConflict
from app.shared.application.unit_of_work import UnitOfWork


def provider_signup_payload(password: str = 'secure-password') -> ProviderSignupCreate:
    return ProviderSignupCreate(
        email='provider@example.com',
        password=password,
        display_name='Provider Test',
    )


def user() -> User:
    return User(
        id=uuid4(),
        email='provider@example.com',
        password_hash='hashed:secure-password',
    )


def user_creator_mock(
    *,
    returned_user: Optional[User] = None,
    error: Optional[Exception] = None,
) -> Mock:
    create_user = Mock(spec=UserCreator)
    create_user.execute = AsyncMock(
        side_effect=error,
        return_value=returned_user or user(),
    )
    return create_user


def provider_repository_mock(
    *,
    existing_slug_id: Optional[UUID] = None,
    provider_by_slug: Optional[Provider] = None,
) -> Mock:
    providers = Mock(spec=ProviderRepository)
    providers.find_id_by_slug = AsyncMock(return_value=existing_slug_id)
    providers.get_by_slug = AsyncMock(return_value=provider_by_slug)
    providers.add = AsyncMock()
    return providers


def unit_of_work_mock(*, commit_error: Optional[Exception] = None) -> Mock:
    unit_of_work = Mock(spec=UnitOfWork)
    unit_of_work.flush = AsyncMock()
    unit_of_work.commit = AsyncMock(side_effect=commit_error)
    unit_of_work.rollback = AsyncMock()
    unit_of_work.refresh = AsyncMock()
    return unit_of_work


def signup_use_case(
    *,
    create_user: Optional[Mock] = None,
    providers: Optional[Mock] = None,
    unit_of_work: Optional[Mock] = None,
    default_timezone: str = 'America/Fortaleza',
) -> SignupProviderUseCase:
    return SignupProviderUseCase(
        create_user=create_user or user_creator_mock(),
        providers=providers or provider_repository_mock(),
        unit_of_work=unit_of_work or unit_of_work_mock(),
        default_timezone=default_timezone,
    )


@pytest.mark.asyncio
async def test_signup_provider_creates_user_and_provider(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    created_user = user()
    create_user = user_creator_mock(returned_user=created_user)
    providers = provider_repository_mock()
    unit_of_work = unit_of_work_mock()
    use_case = signup_use_case(
        create_user=create_user,
        providers=providers,
        unit_of_work=unit_of_work,
    )

    slug = 'provider-test-a1b2c3d4'
    monkeypatch.setattr(
        provider_use_cases,
        'generate_provider_slug',
        lambda display_name: slug,
    )

    provider = await use_case.execute(provider_signup_payload())

    providers.find_id_by_slug.assert_awaited_once_with(slug)
    create_user.execute.assert_awaited_once_with(
        email='provider@example.com',
        password='secure-password',
    )
    unit_of_work.flush.assert_awaited_once_with()
    providers.add.assert_awaited_once_with(provider)
    unit_of_work.commit.assert_awaited_once_with()
    unit_of_work.refresh.assert_awaited_once_with(provider)
    unit_of_work.rollback.assert_not_awaited()

    assert provider.user_id == created_user.id
    assert provider.display_name == 'Provider Test'
    assert provider.slug == slug
    assert provider.timezone == 'America/Fortaleza'
    assert provider.currency_code == 'BRL'
    assert 'provider.signup_succeeded' in {
        getattr(record, 'event_name', None) for record in caplog.records
    }


@pytest.mark.asyncio
async def test_signup_provider_uses_injected_default_timezone_when_payload_omits_it(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_case = signup_use_case(default_timezone='America/Sao_Paulo')

    monkeypatch.setattr(
        provider_use_cases,
        'generate_provider_slug',
        lambda display_name: 'provider-test-a1b2c3d4',
    )

    provider = await use_case.execute(provider_signup_payload())

    assert provider.timezone == 'America/Sao_Paulo'


@pytest.mark.asyncio
async def test_signup_provider_preserves_payload_timezone(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    use_case = signup_use_case(default_timezone='America/Sao_Paulo')

    monkeypatch.setattr(
        provider_use_cases,
        'generate_provider_slug',
        lambda display_name: 'provider-test-a1b2c3d4',
    )

    provider = await use_case.execute(
        ProviderSignupCreate(
            email='provider@example.com',
            password='secure-password',
            display_name='Provider Test',
            timezone='America/Fortaleza',
        )
    )

    assert provider.timezone == 'America/Fortaleza'


def test_signup_payload_rejects_invalid_timezone() -> None:
    with pytest.raises(ValueError):
        ProviderSignupCreate(
            email='provider@example.com',
            password='secure-password',
            display_name='Provider Test',
            timezone='Fortaleza',
        )


@pytest.mark.asyncio
async def test_signup_provider_rejects_invalid_password_before_repositories() -> None:
    create_user = user_creator_mock()
    providers = provider_repository_mock()
    unit_of_work = unit_of_work_mock()
    use_case = signup_use_case(
        create_user=create_user,
        providers=providers,
        unit_of_work=unit_of_work,
    )
    payload = ProviderSignupCreate.model_construct(
        email='provider@example.com',
        password='a' * 7,
        display_name='Provider Test',
        timezone='America/Fortaleza',
        currency_code='BRL',
    )

    with pytest.raises(SignupPasswordPolicyError):
        await use_case.execute(payload)

    providers.find_id_by_slug.assert_not_awaited()
    create_user.execute.assert_not_awaited()
    providers.add.assert_not_awaited()
    unit_of_work.flush.assert_not_awaited()
    unit_of_work.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_signup_provider_rejects_duplicate_email(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    create_user = user_creator_mock(error=UserEmailAlreadyExists())
    providers = provider_repository_mock()
    use_case = signup_use_case(create_user=create_user, providers=providers)

    monkeypatch.setattr(
        provider_use_cases,
        'generate_provider_slug',
        lambda display_name: 'provider-test-a1b2c3d4',
    )

    with pytest.raises(ProviderEmailAlreadyExists):
        await use_case.execute(provider_signup_payload())

    providers.find_id_by_slug.assert_awaited_once_with('provider-test-a1b2c3d4')
    create_user.execute.assert_awaited_once_with(
        email='provider@example.com',
        password='secure-password',
    )
    providers.add.assert_not_awaited()
    assert caplog.records[-1].__dict__['reason'] == 'email_exists'


@pytest.mark.asyncio
async def test_signup_provider_retries_when_slug_exists(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_user = user_creator_mock()
    providers = provider_repository_mock()
    providers.find_id_by_slug = AsyncMock(side_effect=[uuid4(), None])
    unit_of_work = unit_of_work_mock()
    use_case = signup_use_case(
        create_user=create_user,
        providers=providers,
        unit_of_work=unit_of_work,
    )

    slugs = iter(['provider-test-a1b2c3d4', 'provider-test-b5c6d7e8'])
    monkeypatch.setattr(
        provider_use_cases,
        'generate_provider_slug',
        lambda display_name: next(slugs),
    )

    provider = await use_case.execute(provider_signup_payload())

    assert provider.slug == 'provider-test-b5c6d7e8'
    assert providers.find_id_by_slug.await_count == 2
    assert create_user.execute.await_count == 1
    assert providers.add.await_count == 1
    assert unit_of_work.commit.await_count == 1


@pytest.mark.asyncio
async def test_signup_provider_rolls_back_on_unit_of_work_conflict(
    monkeypatch: pytest.MonkeyPatch,
    caplog: pytest.LogCaptureFixture,
) -> None:
    unit_of_work = unit_of_work_mock(commit_error=UnitOfWorkConflict())
    providers = provider_repository_mock()
    use_case = signup_use_case(unit_of_work=unit_of_work, providers=providers)

    monkeypatch.setattr(
        provider_use_cases,
        'generate_provider_slug',
        lambda display_name: 'provider-test-a1b2c3d4',
    )

    with pytest.raises(ProviderSignupConflict):
        await use_case.execute(provider_signup_payload())

    assert unit_of_work.commit.await_count == 5
    assert unit_of_work.rollback.await_count == 5
    unit_of_work.refresh.assert_not_awaited()
    assert caplog.records[-1].__dict__['reason'] == 'slug_conflict_exhausted'


@pytest.mark.asyncio
async def test_signup_provider_retries_after_slug_conflict_on_commit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_user = user_creator_mock()
    providers = provider_repository_mock()
    unit_of_work = unit_of_work_mock()
    unit_of_work.commit = AsyncMock(side_effect=[UnitOfWorkConflict(), None])
    use_case = signup_use_case(
        create_user=create_user,
        providers=providers,
        unit_of_work=unit_of_work,
    )

    slugs = iter(['provider-test-a1b2c3d4', 'provider-test-b5c6d7e8'])
    monkeypatch.setattr(
        provider_use_cases,
        'generate_provider_slug',
        lambda display_name: next(slugs),
    )

    provider = await use_case.execute(provider_signup_payload())

    assert provider.slug == 'provider-test-b5c6d7e8'
    assert create_user.execute.await_count == 2
    assert providers.add.await_count == 2
    assert unit_of_work.commit.await_count == 2
    assert unit_of_work.rollback.await_count == 1


@pytest.mark.asyncio
async def test_get_provider_by_slug_returns_provider() -> None:
    expected_provider = Provider(
        id=uuid4(),
        user_id=uuid4(),
        display_name='Provider Test',
        slug='provider-test',
        timezone='America/Fortaleza',
        currency_code='BRL',
    )
    providers = provider_repository_mock(provider_by_slug=expected_provider)
    use_case = GetProviderBySlugUseCase(providers=providers)

    provider = await use_case.execute('provider-test')

    providers.get_by_slug.assert_awaited_once_with('provider-test')
    assert provider is expected_provider


@pytest.mark.asyncio
async def test_get_provider_by_slug_raises_when_missing() -> None:
    providers = provider_repository_mock()
    use_case = GetProviderBySlugUseCase(providers=providers)

    with pytest.raises(ProviderNotFound):
        await use_case.execute('missing-provider')

    providers.get_by_slug.assert_awaited_once_with('missing-provider')
