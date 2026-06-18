from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest

from app.modules.offerings.application.exceptions import OfferingNotFound
from app.modules.offerings.application.output_ports import OfferingRepository
from app.modules.offerings.application.use_cases import (
    CreateOfferingUseCase,
    ListActiveProviderOfferingsUseCase,
    ListProviderOfferingsUseCase,
    UpdateOfferingUseCase,
)
from app.modules.offerings.infrastructure.models import Offering
from app.modules.offerings.schemas.catalog import OfferingCreate, OfferingUpdate
from app.modules.providers.application.exceptions import (
    ProviderAccessForbidden,
    ProviderNotFound,
)
from app.modules.providers.application.output_ports import ProviderRepository
from app.modules.providers.infrastructure.models import Provider
from app.shared.application.unit_of_work import UnitOfWork


def provider() -> Provider:
    return Provider(
        id=uuid4(),
        user_id=uuid4(),
        display_name='Provider Test',
        slug='provider-test',
        timezone='America/Fortaleza',
        currency_code='BRL',
    )


def offering(provider_id: UUID) -> Offering:
    return Offering(
        id=uuid4(),
        provider_id=provider_id,
        title='Consulta',
        description='Atendimento inicial',
        duration_minutes=30,
        price_cents=15000,
        is_active=True,
    )


def provider_repository_mock(
    *,
    provider_by_id: Provider | None = None,
    provider_by_slug: Provider | None = None,
) -> Mock:
    providers = Mock(spec=ProviderRepository)
    providers.get_by_id = AsyncMock(return_value=provider_by_id)
    providers.get_by_slug = AsyncMock(return_value=provider_by_slug)
    return providers


def offering_repository_mock(
    *,
    offering_by_id: Offering | None = None,
    active_offerings: list[Offering] | None = None,
) -> Mock:
    offerings = Mock(spec=OfferingRepository)
    offerings.get_by_id = AsyncMock(return_value=offering_by_id)
    offerings.list_active_by_provider_id = AsyncMock(
        return_value=active_offerings or []
    )
    offerings.list_by_provider_id = AsyncMock(return_value=active_offerings or [])
    offerings.add = AsyncMock()
    offerings.get_active_by_id = AsyncMock(return_value=offering_by_id)
    return offerings


def unit_of_work_mock() -> Mock:
    unit_of_work = Mock(spec=UnitOfWork)
    unit_of_work.commit = AsyncMock()
    unit_of_work.refresh = AsyncMock()
    return unit_of_work


@pytest.mark.asyncio
async def test_create_offering_creates_offering_for_existing_provider() -> None:
    existing_provider = provider()
    providers = provider_repository_mock(provider_by_id=existing_provider)
    offerings = offering_repository_mock()
    unit_of_work = unit_of_work_mock()
    use_case = CreateOfferingUseCase(
        providers=providers,
        offerings=offerings,
        unit_of_work=unit_of_work,
    )
    payload = OfferingCreate(
        title='Consulta',
        description='Atendimento inicial',
        duration_minutes=30,
        price_cents=15000,
    )

    created = await use_case.execute(
        existing_provider.id,
        payload,
        existing_provider.id,
    )

    providers.get_by_id.assert_awaited_once_with(existing_provider.id)
    offerings.add.assert_awaited_once_with(created)
    unit_of_work.commit.assert_awaited_once_with()
    unit_of_work.refresh.assert_awaited_once_with(created)
    assert created.provider_id == existing_provider.id
    assert created.title == 'Consulta'
    assert created.description == 'Atendimento inicial'
    assert created.duration_minutes == 30
    assert created.price_cents == 15000
    assert created.is_active is True


@pytest.mark.asyncio
async def test_create_offering_raises_when_provider_is_missing() -> None:
    missing_provider_id = uuid4()
    providers = provider_repository_mock()
    offerings = offering_repository_mock()
    unit_of_work = unit_of_work_mock()
    use_case = CreateOfferingUseCase(
        providers=providers,
        offerings=offerings,
        unit_of_work=unit_of_work,
    )
    payload = OfferingCreate(title='Consulta', duration_minutes=30)

    with pytest.raises(ProviderNotFound):
        await use_case.execute(missing_provider_id, payload, uuid4())

    providers.get_by_id.assert_awaited_once_with(missing_provider_id)
    offerings.add.assert_not_awaited()
    unit_of_work.commit.assert_not_awaited()
    unit_of_work.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_offering_raises_when_provider_is_not_owned() -> None:
    existing_provider = provider()
    providers = provider_repository_mock(provider_by_id=existing_provider)
    offerings = offering_repository_mock()
    unit_of_work = unit_of_work_mock()
    use_case = CreateOfferingUseCase(
        providers=providers,
        offerings=offerings,
        unit_of_work=unit_of_work,
    )
    payload = OfferingCreate(title='Consulta', duration_minutes=30)

    with pytest.raises(ProviderAccessForbidden):
        await use_case.execute(existing_provider.id, payload, uuid4())

    offerings.add.assert_not_awaited()
    unit_of_work.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_active_provider_offerings_returns_offerings() -> None:
    existing_provider = provider()
    expected_offering = offering(existing_provider.id)
    providers = provider_repository_mock(provider_by_slug=existing_provider)
    offerings = offering_repository_mock(active_offerings=[expected_offering])
    use_case = ListActiveProviderOfferingsUseCase(
        providers=providers,
        offerings=offerings,
    )

    result = await use_case.execute('provider-test')

    providers.get_by_slug.assert_awaited_once_with('provider-test')
    offerings.list_active_by_provider_id.assert_awaited_once_with(existing_provider.id)
    assert result == [expected_offering]


@pytest.mark.asyncio
async def test_list_active_provider_offerings_raises_when_provider_is_missing() -> None:
    providers = provider_repository_mock()
    offerings = offering_repository_mock()
    use_case = ListActiveProviderOfferingsUseCase(
        providers=providers,
        offerings=offerings,
    )

    with pytest.raises(ProviderNotFound):
        await use_case.execute('missing-provider')

    providers.get_by_slug.assert_awaited_once_with('missing-provider')
    offerings.list_active_by_provider_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_provider_offerings_returns_owned_offerings() -> None:
    existing_provider = provider()
    expected_offering = offering(existing_provider.id)
    providers = provider_repository_mock(provider_by_id=existing_provider)
    offerings = offering_repository_mock(active_offerings=[expected_offering])
    use_case = ListProviderOfferingsUseCase(
        providers=providers,
        offerings=offerings,
    )

    result = await use_case.execute(existing_provider.id, existing_provider.id)

    providers.get_by_id.assert_awaited_once_with(existing_provider.id)
    offerings.list_by_provider_id.assert_awaited_once_with(existing_provider.id)
    assert result == [expected_offering]


@pytest.mark.asyncio
async def test_list_provider_offerings_raises_when_provider_is_not_owned() -> None:
    existing_provider = provider()
    providers = provider_repository_mock(provider_by_id=existing_provider)
    offerings = offering_repository_mock()
    use_case = ListProviderOfferingsUseCase(
        providers=providers,
        offerings=offerings,
    )

    with pytest.raises(ProviderAccessForbidden):
        await use_case.execute(existing_provider.id, uuid4())

    offerings.list_by_provider_id.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_offering_updates_only_sent_fields() -> None:
    existing_offering = offering(uuid4())
    offerings = offering_repository_mock(offering_by_id=existing_offering)
    unit_of_work = unit_of_work_mock()
    use_case = UpdateOfferingUseCase(
        offerings=offerings,
        unit_of_work=unit_of_work,
    )
    payload = OfferingUpdate(title='Consulta atualizada', is_active=False)

    updated = await use_case.execute(
        existing_offering.id,
        payload,
        existing_offering.provider_id,
    )

    offerings.get_by_id.assert_awaited_once_with(existing_offering.id)
    unit_of_work.commit.assert_awaited_once_with()
    unit_of_work.refresh.assert_awaited_once_with(updated)
    assert updated is existing_offering
    assert updated.title == 'Consulta atualizada'
    assert updated.is_active is False
    assert updated.description == 'Atendimento inicial'
    assert updated.duration_minutes == 30
    assert updated.price_cents == 15000


@pytest.mark.asyncio
async def test_update_offering_raises_when_offering_is_missing() -> None:
    missing_offering_id = uuid4()
    offerings = offering_repository_mock()
    unit_of_work = unit_of_work_mock()
    use_case = UpdateOfferingUseCase(
        offerings=offerings,
        unit_of_work=unit_of_work,
    )
    payload = OfferingUpdate(title='Consulta atualizada')

    with pytest.raises(OfferingNotFound):
        await use_case.execute(missing_offering_id, payload, uuid4())

    offerings.get_by_id.assert_awaited_once_with(missing_offering_id)
    unit_of_work.commit.assert_not_awaited()
    unit_of_work.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_offering_raises_when_offering_is_not_owned() -> None:
    existing_offering = offering(uuid4())
    offerings = offering_repository_mock(offering_by_id=existing_offering)
    unit_of_work = unit_of_work_mock()
    use_case = UpdateOfferingUseCase(
        offerings=offerings,
        unit_of_work=unit_of_work,
    )
    payload = OfferingUpdate(title='Consulta atualizada')

    with pytest.raises(ProviderAccessForbidden):
        await use_case.execute(existing_offering.id, payload, uuid4())

    unit_of_work.commit.assert_not_awaited()
    unit_of_work.refresh.assert_not_awaited()
