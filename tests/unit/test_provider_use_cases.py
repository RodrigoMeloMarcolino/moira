from uuid import UUID, uuid4

import pytest

from app.modules.auth.domain.password_policy import SignupPasswordPolicyError
from app.modules.providers.application.exceptions import (
    ProviderEmailAlreadyExists,
    ProviderNotFound,
    ProviderSignupConflict,
    ProviderSlugAlreadyExists,
)
from app.modules.providers.application.use_cases import (
    GetProviderBySlugUseCase,
    SignupProviderUseCase,
)
from app.modules.providers.infrastructure.models import Provider
from app.modules.providers.schemas.catalog import ProviderSignupCreate
from app.modules.users.application.exceptions import UserEmailAlreadyExists
from app.modules.users.infrastructure.models import User
from app.shared.application.exceptions import UnitOfWorkConflict


class FakeCreateUserUseCase:
    def __init__(self, error: Exception | None = None) -> None:
        self.error = error
        self.created: list[tuple[str, str]] = []
        self.users: list[User] = []

    async def execute(self, *, email: str, password: str) -> User:
        if self.error is not None:
            raise self.error

        user = User(
            id=uuid4(),
            email=email,
            password_hash=f"hashed:{password}",
        )
        self.created.append((email, password))
        self.users.append(user)
        return user


class FakeProviderRepository:
    def __init__(
        self,
        *,
        existing_slug_id: UUID | None = None,
        provider_by_slug: Provider | None = None,
    ) -> None:
        self.existing_slug_id = existing_slug_id
        self.provider_by_slug = provider_by_slug
        self.added: list[Provider] = []

    async def find_id_by_slug(self, slug: str) -> UUID | None:
        _ = slug
        return self.existing_slug_id

    async def get_by_id(self, provider_id: UUID) -> Provider | None:
        _ = provider_id
        return None

    async def get_by_slug(self, slug: str) -> Provider | None:
        _ = slug
        return self.provider_by_slug

    async def add(self, provider: Provider) -> None:
        self.added.append(provider)


class FakeUnitOfWork:
    def __init__(self, commit_error: Exception | None = None) -> None:
        self.commit_error = commit_error
        self.committed = False
        self.flushed = False
        self.refreshed: object | None = None
        self.rolled_back = False

    async def flush(self) -> None:
        self.flushed = True

    async def commit(self) -> None:
        if self.commit_error is not None:
            raise self.commit_error

        self.committed = True

    async def rollback(self) -> None:
        self.rolled_back = True

    async def refresh(self, entity: object) -> None:
        self.refreshed = entity
        if isinstance(entity, Provider) and entity.id is None:
            entity.id = uuid4()


def provider_signup_payload(password: str = "secure-password") -> ProviderSignupCreate:
    return ProviderSignupCreate(
        email="provider@example.com",
        password=password,
        display_name="Provider Test",
        slug="provider-test",
    )


def signup_use_case(
    *,
    create_user: FakeCreateUserUseCase | None = None,
    providers: FakeProviderRepository | None = None,
    unit_of_work: FakeUnitOfWork | None = None,
) -> SignupProviderUseCase:
    return SignupProviderUseCase(
        create_user=create_user or FakeCreateUserUseCase(),
        providers=providers or FakeProviderRepository(),
        unit_of_work=unit_of_work or FakeUnitOfWork(),
    )


@pytest.mark.asyncio
async def test_signup_provider_creates_user_and_provider() -> None:
    create_user = FakeCreateUserUseCase()
    providers = FakeProviderRepository()
    unit_of_work = FakeUnitOfWork()
    use_case = signup_use_case(
        create_user=create_user,
        providers=providers,
        unit_of_work=unit_of_work,
    )

    provider = await use_case.execute(provider_signup_payload())

    assert unit_of_work.flushed is True
    assert unit_of_work.committed is True
    assert unit_of_work.refreshed is provider

    assert create_user.created == [("provider@example.com", "secure-password")]
    assert len(create_user.users) == 1
    user = create_user.users[0]
    assert user.email == "provider@example.com"
    assert user.password_hash == "hashed:secure-password"

    assert providers.added == [provider]
    assert provider.user_id == user.id
    assert provider.display_name == "Provider Test"
    assert provider.slug == "provider-test"
    assert provider.timezone == "America/Fortaleza"
    assert provider.currency_code == "BRL"


@pytest.mark.asyncio
async def test_signup_provider_rejects_invalid_password_before_repositories() -> None:
    create_user = FakeCreateUserUseCase()
    providers = FakeProviderRepository()
    use_case = signup_use_case(create_user=create_user, providers=providers)
    payload = ProviderSignupCreate.model_construct(
        email="provider@example.com",
        password="a" * 7,
        display_name="Provider Test",
        slug="provider-test",
        timezone="America/Fortaleza",
        currency_code="BRL",
    )

    with pytest.raises(SignupPasswordPolicyError):
        await use_case.execute(payload)

    assert create_user.created == []
    assert providers.added == []


@pytest.mark.asyncio
async def test_signup_provider_rejects_duplicate_email() -> None:
    create_user = FakeCreateUserUseCase(error=UserEmailAlreadyExists())
    use_case = signup_use_case(create_user=create_user)

    with pytest.raises(ProviderEmailAlreadyExists):
        await use_case.execute(provider_signup_payload())


@pytest.mark.asyncio
async def test_signup_provider_rejects_duplicate_slug() -> None:
    providers = FakeProviderRepository(existing_slug_id=uuid4())
    use_case = signup_use_case(providers=providers)

    with pytest.raises(ProviderSlugAlreadyExists):
        await use_case.execute(provider_signup_payload())


@pytest.mark.asyncio
async def test_signup_provider_rolls_back_on_unit_of_work_conflict() -> None:
    unit_of_work = FakeUnitOfWork(commit_error=UnitOfWorkConflict())
    use_case = signup_use_case(unit_of_work=unit_of_work)

    with pytest.raises(ProviderSignupConflict):
        await use_case.execute(provider_signup_payload())

    assert unit_of_work.rolled_back is True
    assert unit_of_work.committed is False


@pytest.mark.asyncio
async def test_get_provider_by_slug_returns_provider() -> None:
    expected_provider = Provider(
        id=uuid4(),
        user_id=uuid4(),
        display_name="Provider Test",
        slug="provider-test",
        timezone="America/Fortaleza",
        currency_code="BRL",
    )
    use_case = GetProviderBySlugUseCase(
        providers=FakeProviderRepository(provider_by_slug=expected_provider)
    )

    provider = await use_case.execute("provider-test")

    assert provider is expected_provider


@pytest.mark.asyncio
async def test_get_provider_by_slug_raises_when_missing() -> None:
    use_case = GetProviderBySlugUseCase(providers=FakeProviderRepository())

    with pytest.raises(ProviderNotFound):
        await use_case.execute("missing-provider")
