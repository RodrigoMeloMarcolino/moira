from uuid import UUID

from app.modules.availability.application.public_cache import PublicAvailabilityCache
from app.modules.offerings.application.exceptions import OfferingNotFound
from app.modules.offerings.application.output_ports import OfferingRepository
from app.modules.offerings.application.public_cache import PublicOfferingsCache
from app.modules.offerings.infrastructure.models import Offering
from app.modules.offerings.schemas.catalog import (
    OfferingCreate,
    OfferingPublic,
    OfferingUpdate,
)
from app.modules.providers.application.exceptions import (
    ProviderAccessForbidden,
    ProviderNotFound,
)
from app.modules.providers.application.output_ports import ProviderRepository
from app.shared.application.unit_of_work import UnitOfWork


class CreateOfferingUseCase:
    def __init__(
        self,
        offerings: OfferingRepository,
        unit_of_work: UnitOfWork,
        public_offerings_cache: PublicOfferingsCache | None = None,
    ) -> None:
        self.offerings = offerings
        self.unit_of_work = unit_of_work
        self.public_offerings_cache = public_offerings_cache

    async def execute(
        self,
        payload: OfferingCreate,
        current_provider_id: UUID,
    ) -> Offering:
        offering = Offering(provider_id=current_provider_id, **payload.model_dump())
        await self.offerings.add(offering)
        await self.unit_of_work.commit()
        if self.public_offerings_cache is not None:
            await self.public_offerings_cache.invalidate(current_provider_id)
        await self.unit_of_work.refresh(offering)

        return offering


class ListActiveProviderOfferingsUseCase:
    def __init__(
        self,
        providers: ProviderRepository,
        offerings: OfferingRepository,
    ) -> None:
        self.providers = providers
        self.offerings = offerings

    async def execute(self, slug: str) -> list[Offering]:
        provider = await self.providers.get_by_slug(slug)
        if provider is None:
            raise ProviderNotFound

        return await self.offerings.list_active_by_provider_id(provider.id)


class ListPublicProviderOfferingsUseCase:
    def __init__(
        self,
        providers: ProviderRepository,
        offerings: OfferingRepository,
        public_cache: PublicOfferingsCache | None = None,
    ) -> None:
        self.providers = providers
        self.offerings = offerings
        self.public_cache = public_cache

    async def execute(self, slug: str) -> list[OfferingPublic]:
        provider = await self.providers.get_by_slug(slug)
        if provider is None:
            raise ProviderNotFound

        if self.public_cache is not None:
            cached_offerings = await self.public_cache.get(provider.id)
            if cached_offerings is not None:
                return cached_offerings

        offerings = await self.offerings.list_active_by_provider_id(provider.id)
        public_offerings = [
            OfferingPublic.model_validate(offering) for offering in offerings
        ]
        if self.public_cache is not None:
            await self.public_cache.set(provider.id, public_offerings)

        return public_offerings


class ListProviderOfferingsUseCase:
    def __init__(
        self,
        offerings: OfferingRepository,
    ) -> None:
        self.offerings = offerings

    async def execute(self, current_provider_id: UUID) -> list[Offering]:
        return await self.offerings.list_by_provider_id(current_provider_id)


class UpdateOfferingUseCase:
    def __init__(
        self,
        offerings: OfferingRepository,
        unit_of_work: UnitOfWork,
        public_offerings_cache: PublicOfferingsCache | None = None,
        public_availability_cache: PublicAvailabilityCache | None = None,
    ) -> None:
        self.offerings = offerings
        self.unit_of_work = unit_of_work
        self.public_offerings_cache = public_offerings_cache
        self.public_availability_cache = public_availability_cache

    async def execute(
        self,
        offering_id: UUID,
        payload: OfferingUpdate,
        current_provider_id: UUID,
    ) -> Offering:
        offering = await self.offerings.get_by_id(offering_id)
        if offering is None:
            raise OfferingNotFound

        if offering.provider_id != current_provider_id:
            raise ProviderAccessForbidden

        changes = payload.model_dump(exclude_unset=True)
        should_bump_schedule_version = (
            'duration_minutes' in changes
            and changes['duration_minutes'] != offering.duration_minutes
        ) or ('is_active' in changes and changes['is_active'] != offering.is_active)

        for field, value in changes.items():
            setattr(offering, field, value)

        await self.unit_of_work.commit()
        if self.public_offerings_cache is not None:
            await self.public_offerings_cache.invalidate(current_provider_id)
        if should_bump_schedule_version and self.public_availability_cache is not None:
            await self.public_availability_cache.bump_schedule_version(
                current_provider_id
            )
        await self.unit_of_work.refresh(offering)

        return offering
