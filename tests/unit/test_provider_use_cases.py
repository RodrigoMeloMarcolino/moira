from uuid import UUID, uuid4

import pytest

from app.modules.auth.domain.password_policy import SignupPasswordPolicyError
from app.modules.auth.infrastructure.models import User
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
from app.shared.application.exceptions import UnitOfWorkConflict


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


class FakePasswordHasher:
    def __init__(self) -> None:
        self.hashed_passwords: list[str] = []

    def hash(self, password: str) -> str:
        self.hashed_passwords.append(password)
        return f"hashed:{password}"

    def verify(self, password: str, password_hash: str) -> bool:
        return password_hash == f"hashed:{password}"


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
    users: FakeUserRepository | None = None,
    providers: FakeProviderRepository | None = None,
    hasher: FakePasswordHasher | None = None,
    unit_of_work: FakeUnitOfWork | None = None,
) -> SignupProviderUseCase:
    return SignupProviderUseCase(
        users=users or FakeUserRepository(),
        providers=providers or FakeProviderRepository(),
        password_hasher=hasher or FakePasswordHasher(),
        unit_of_work=unit_of_work or FakeUnitOfWork(),
    )


@pytest.mark.asyncio
async def test_signup_provider_creates_user_and_provider() -> None:
    users = FakeUserRepository()
    providers = FakeProviderRepository()
    hasher = FakePasswordHasher()
    unit_of_work = FakeUnitOfWork()
    use_case = signup_use_case(
        users=users,
        providers=providers,
        hasher=hasher,
        unit_of_work=unit_of_work,
    )

    provider = await use_case.execute(provider_signup_payload())

    assert unit_of_work.flushed is True
    assert unit_of_work.committed is True
    assert unit_of_work.refreshed is provider
    assert hasher.hashed_passwords == ["secure-password"]

    assert len(users.added) == 1
    user = users.added[0]
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
    users = FakeUserRepository()
    providers = FakeProviderRepository()
    use_case = signup_use_case(users=users, providers=providers)
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

    assert users.added == []
    assert providers.added == []


@pytest.mark.asyncio
async def test_signup_provider_rejects_duplicate_email() -> None:
    users = FakeUserRepository(existing_email_id=uuid4())
    use_case = signup_use_case(users=users)

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
