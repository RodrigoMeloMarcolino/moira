from app.modules.auth.domain.password_policy import validate_signup_password
from app.modules.providers.application.exceptions import (
    ProviderEmailAlreadyExists,
    ProviderNotFound,
    ProviderSignupConflict,
)
from app.modules.providers.application.output_ports import ProviderRepository
from app.modules.providers.domain.slug import generate_provider_slug
from app.modules.providers.infrastructure.models import Provider
from app.modules.providers.schemas.catalog import ProviderSignupCreate
from app.modules.users.application.exceptions import UserEmailAlreadyExists
from app.modules.users.application.input_ports import UserCreator
from app.shared.application.exceptions import UnitOfWorkConflict
from app.shared.application.unit_of_work import UnitOfWork

MAX_PROVIDER_SLUG_GENERATION_ATTEMPTS = 5


class SignupProviderUseCase:
    def __init__(
        self,
        create_user: UserCreator,
        providers: ProviderRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self.create_user = create_user
        self.providers = providers
        self.unit_of_work = unit_of_work

    async def execute(self, payload: ProviderSignupCreate) -> Provider:
        validate_signup_password(payload.password)

        for _ in range(MAX_PROVIDER_SLUG_GENERATION_ATTEMPTS):
            slug = generate_provider_slug(payload.display_name)
            existing_slug = await self.providers.find_id_by_slug(slug)
            if existing_slug is not None:
                continue

            try:
                user = await self.create_user.execute(
                    email=payload.email,
                    password=payload.password,
                )
            except UserEmailAlreadyExists as exc:
                raise ProviderEmailAlreadyExists from exc

            try:
                await self.unit_of_work.flush()
            except UnitOfWorkConflict:
                await self.unit_of_work.rollback()
                continue

            provider = Provider(
                user_id=user.id,
                display_name=payload.display_name,
                slug=slug,
                timezone=payload.timezone,
                currency_code=payload.currency_code,
            )
            await self.providers.add(provider)

            try:
                await self.unit_of_work.commit()
            except UnitOfWorkConflict:
                await self.unit_of_work.rollback()
                continue

            await self.unit_of_work.refresh(provider)
            return provider

        raise ProviderSignupConflict


class GetProviderBySlugUseCase:
    def __init__(self, providers: ProviderRepository) -> None:
        self.providers = providers

    async def execute(self, slug: str) -> Provider:
        provider = await self.providers.get_by_slug(slug)
        if provider is None:
            raise ProviderNotFound

        return provider
