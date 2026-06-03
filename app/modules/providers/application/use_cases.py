from app.modules.auth.application.ports import PasswordHasher
from app.modules.auth.domain.password_policy import validate_signup_password
from app.modules.auth.infrastructure.models import User
from app.modules.providers.application.exceptions import (
    ProviderEmailAlreadyExists,
    ProviderNotFound,
    ProviderSignupConflict,
    ProviderSlugAlreadyExists,
)
from app.modules.providers.application.ports import ProviderRepository, UserRepository
from app.modules.providers.infrastructure.models import Provider
from app.modules.providers.schemas.catalog import ProviderSignupCreate
from app.shared.application.exceptions import UnitOfWorkConflict
from app.shared.application.unit_of_work import UnitOfWork


class SignupProviderUseCase:
    def __init__(
        self,
        users: UserRepository,
        providers: ProviderRepository,
        password_hasher: PasswordHasher,
        unit_of_work: UnitOfWork,
    ) -> None:
        self.users = users
        self.providers = providers
        self.password_hasher = password_hasher
        self.unit_of_work = unit_of_work

    async def execute(self, payload: ProviderSignupCreate) -> Provider:
        validate_signup_password(payload.password)

        existing_email = await self.users.find_id_by_email(payload.email)
        if existing_email is not None:
            raise ProviderEmailAlreadyExists

        existing_slug = await self.providers.find_id_by_slug(payload.slug)
        if existing_slug is not None:
            raise ProviderSlugAlreadyExists

        user = User(
            email=payload.email,
            password_hash=self.password_hasher.hash(payload.password),
        )
        await self.users.add(user)
        await self.unit_of_work.flush()

        provider = Provider(
            user_id=user.id,
            display_name=payload.display_name,
            slug=payload.slug,
            timezone=payload.timezone,
            currency_code=payload.currency_code,
        )
        await self.providers.add(provider)

        try:
            await self.unit_of_work.commit()
        except UnitOfWorkConflict as exc:
            await self.unit_of_work.rollback()
            raise ProviderSignupConflict from exc

        await self.unit_of_work.refresh(provider)
        return provider


class GetProviderBySlugUseCase:
    def __init__(self, providers: ProviderRepository) -> None:
        self.providers = providers

    async def execute(self, slug: str) -> Provider:
        provider = await self.providers.get_by_slug(slug)
        if provider is None:
            raise ProviderNotFound

        return provider
