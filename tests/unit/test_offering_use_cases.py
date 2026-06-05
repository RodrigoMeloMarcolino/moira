from uuid import UUID, uuid4

import pytest

from app.modules.offerings.application.exceptions import OfferingNotFound
from app.modules.offerings.application.use_cases import (
    CreateOfferingUseCase,
    ListActiveProviderOfferingsUseCase,
    UpdateOfferingUseCase,
)
from app.modules.offerings.infrastructure.models import Offering
from app.modules.offerings.schemas.catalog import OfferingCreate, OfferingUpdate
from app.modules.providers.application.exceptions import ProviderNotFound
from app.modules.providers.infrastructure.models import Provider


class FakeProviderRepository:
    def __init__(
        self,
        *,
        provider_by_id: Provider | None = None,
        provider_by_slug: Provider | None = None,
    ) -> None:
        self.provider_by_id = provider_by_id
        self.provider_by_slug = provider_by_slug

    async def find_id_by_slug(self, slug: str) -> UUID | None:
        _ = slug
        return None

    async def get_by_id(self, provider_id: UUID) -> Provider | None:
        _ = provider_id
        return self.provider_by_id

    async def get_by_slug(self, slug: str) -> Provider | None:
        _ = slug
        return self.provider_by_slug

    async def add(self, provider: Provider) -> None:
        _ = provider
        return None


class FakeOfferingRepository:
    def __init__(
        self,
        *,
        offering_by_id: Offering | None = None,
        active_offerings: list[Offering] | None = None,
    ) -> None:
        self.offering_by_id = offering_by_id
        self.active_offerings = active_offerings or []
        self.added: list[Offering] = []

    async def get_by_id(self, offering_id: UUID) -> Offering | None:
        _ = offering_id
        return self.offering_by_id

    async def list_active_by_provider_id(self, provider_id: UUID) -> list[Offering]:
        _ = provider_id
        return self.active_offerings

    async def add(self, offering: Offering) -> None:
        self.added.append(offering)


class FakeUnitOfWork:
    def __init__(self) -> None:
        self.committed = False
        self.refreshed: object | None = None

    async def flush(self) -> None:
        return None

    async def commit(self) -> None:
        self.committed = True

    async def rollback(self) -> None:
        return None

    async def refresh(self, entity: object) -> None:
        self.refreshed = entity
        if isinstance(entity, Offering) and entity.id is None:
            entity.id = uuid4()


def provider() -> Provider:
    return Provider(
        id=uuid4(),
        user_id=uuid4(),
        display_name="Provider Test",
        slug="provider-test",
        timezone="America/Fortaleza",
        currency_code="BRL",
    )


def offering(provider_id: UUID) -> Offering:
    return Offering(
        id=uuid4(),
        provider_id=provider_id,
        title="Consulta",
        description="Atendimento inicial",
        duration_minutes=30,
        price_cents=15000,
        is_active=True,
    )


@pytest.mark.asyncio
async def test_create_offering_creates_offering_for_existing_provider() -> None:
    existing_provider = provider()
    offerings = FakeOfferingRepository()
    unit_of_work = FakeUnitOfWork()
    use_case = CreateOfferingUseCase(
        providers=FakeProviderRepository(provider_by_id=existing_provider),
        offerings=offerings,
        unit_of_work=unit_of_work,
    )
    payload = OfferingCreate(
        title="Consulta",
        description="Atendimento inicial",
        duration_minutes=30,
        price_cents=15000,
    )

    created = await use_case.execute(existing_provider.id, payload)

    assert unit_of_work.committed is True
    assert unit_of_work.refreshed is created
    assert offerings.added == [created]
    assert created.provider_id == existing_provider.id
    assert created.title == "Consulta"
    assert created.description == "Atendimento inicial"
    assert created.duration_minutes == 30
    assert created.price_cents == 15000
    assert created.is_active is True


@pytest.mark.asyncio
async def test_create_offering_raises_when_provider_is_missing() -> None:
    offerings = FakeOfferingRepository()
    unit_of_work = FakeUnitOfWork()
    use_case = CreateOfferingUseCase(
        providers=FakeProviderRepository(),
        offerings=offerings,
        unit_of_work=unit_of_work,
    )
    payload = OfferingCreate(title="Consulta", duration_minutes=30)

    with pytest.raises(ProviderNotFound):
        await use_case.execute(uuid4(), payload)

    assert offerings.added == []
    assert unit_of_work.committed is False


@pytest.mark.asyncio
async def test_list_active_provider_offerings_returns_offerings() -> None:
    existing_provider = provider()
    expected_offering = offering(existing_provider.id)
    use_case = ListActiveProviderOfferingsUseCase(
        providers=FakeProviderRepository(provider_by_slug=existing_provider),
        offerings=FakeOfferingRepository(active_offerings=[expected_offering]),
    )

    offerings = await use_case.execute("provider-test")

    assert offerings == [expected_offering]


@pytest.mark.asyncio
async def test_list_active_provider_offerings_raises_when_provider_is_missing() -> None:
    use_case = ListActiveProviderOfferingsUseCase(
        providers=FakeProviderRepository(),
        offerings=FakeOfferingRepository(),
    )

    with pytest.raises(ProviderNotFound):
        await use_case.execute("missing-provider")


@pytest.mark.asyncio
async def test_update_offering_updates_only_sent_fields() -> None:
    existing_offering = offering(uuid4())
    unit_of_work = FakeUnitOfWork()
    use_case = UpdateOfferingUseCase(
        offerings=FakeOfferingRepository(offering_by_id=existing_offering),
        unit_of_work=unit_of_work,
    )
    payload = OfferingUpdate(title="Consulta atualizada", is_active=False)

    updated = await use_case.execute(existing_offering.id, payload)

    assert unit_of_work.committed is True
    assert unit_of_work.refreshed is updated
    assert updated is existing_offering
    assert updated.title == "Consulta atualizada"
    assert updated.is_active is False
    assert updated.description == "Atendimento inicial"
    assert updated.duration_minutes == 30
    assert updated.price_cents == 15000


@pytest.mark.asyncio
async def test_update_offering_raises_when_offering_is_missing() -> None:
    unit_of_work = FakeUnitOfWork()
    use_case = UpdateOfferingUseCase(
        offerings=FakeOfferingRepository(),
        unit_of_work=unit_of_work,
    )
    payload = OfferingUpdate(title="Consulta atualizada")

    with pytest.raises(OfferingNotFound):
        await use_case.execute(uuid4(), payload)

    assert unit_of_work.committed is False
