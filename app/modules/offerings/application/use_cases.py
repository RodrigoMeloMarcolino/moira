from uuid import UUID

from app.modules.offerings.application.exceptions import OfferingNotFound
from app.modules.offerings.application.output_ports import OfferingRepository
from app.modules.offerings.infrastructure.models import Offering
from app.modules.offerings.schemas.catalog import OfferingCreate, OfferingUpdate
from app.modules.providers.application.exceptions import (
    ProviderAccessForbidden,
    ProviderNotFound,
)
from app.modules.providers.application.output_ports import ProviderRepository
from app.shared.application.unit_of_work import UnitOfWork


class CreateOfferingUseCase:
    def __init__(
        self,
        providers: ProviderRepository,
        offerings: OfferingRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self.providers = providers
        self.offerings = offerings
        self.unit_of_work = unit_of_work

    async def execute(
        self,
        provider_id: UUID,
        payload: OfferingCreate,
        current_provider_id: UUID,
    ) -> Offering:
        provider = await self.providers.get_by_id(provider_id)
        if provider is None:
            raise ProviderNotFound

        if provider.id != current_provider_id:
            raise ProviderAccessForbidden

        offering = Offering(provider_id=provider.id, **payload.model_dump())
        await self.offerings.add(offering)
        await self.unit_of_work.commit()
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


class ListProviderOfferingsUseCase:
    def __init__(
        self,
        providers: ProviderRepository,
        offerings: OfferingRepository,
    ) -> None:
        self.providers = providers
        self.offerings = offerings

    async def execute(
        self,
        provider_id: UUID,
        current_provider_id: UUID,
    ) -> list[Offering]:
        provider = await self.providers.get_by_id(provider_id)
        if provider is None:
            raise ProviderNotFound

        if provider.id != current_provider_id:
            raise ProviderAccessForbidden

        return await self.offerings.list_by_provider_id(provider.id)


class UpdateOfferingUseCase:
    def __init__(
        self,
        offerings: OfferingRepository,
        unit_of_work: UnitOfWork,
    ) -> None:
        self.offerings = offerings
        self.unit_of_work = unit_of_work

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

        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(offering, field, value)

        await self.unit_of_work.commit()
        await self.unit_of_work.refresh(offering)

        return offering
