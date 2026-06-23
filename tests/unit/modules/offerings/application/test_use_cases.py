import logging
from typing import Optional
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest

from app.modules.availability.application.public_cache import PublicAvailabilityCache
from app.modules.offerings.application.exceptions import OfferingNotFound
from app.modules.offerings.application.output_ports import OfferingRepository
from app.modules.offerings.application.public_cache import PublicOfferingsCache
from app.modules.offerings.application.use_cases import (
    CreateOfferingUseCase,
    ListActiveProviderOfferingsUseCase,
    ListProviderOfferingsUseCase,
    ListPublicProviderOfferingsUseCase,
    UpdateOfferingUseCase,
)
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
    provider_by_id: Optional[Provider] = None,
    provider_by_slug: Optional[Provider] = None,
) -> Mock:
    providers = Mock(spec=ProviderRepository)
    providers.get_by_id = AsyncMock(return_value=provider_by_id)
    providers.get_by_slug = AsyncMock(return_value=provider_by_slug)
    return providers


def offering_repository_mock(
    *,
    offering_by_id: Optional[Offering] = None,
    active_offerings: Optional[list[Offering]] = None,
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


def public_offerings_cache_mock() -> Mock:
    cache = Mock(spec=PublicOfferingsCache)
    cache.get = AsyncMock(return_value=None)
    cache.set = AsyncMock()
    cache.invalidate = AsyncMock()
    return cache


def public_availability_cache_mock() -> Mock:
    cache = Mock(spec=PublicAvailabilityCache)
    cache.bump_schedule_version = AsyncMock(return_value=2)
    return cache


@pytest.mark.asyncio
async def test_create_offering_creates_offering_for_existing_provider(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    existing_provider = provider()
    offerings = offering_repository_mock()
    unit_of_work = unit_of_work_mock()
    public_offerings_cache = public_offerings_cache_mock()
    use_case = CreateOfferingUseCase(
        offerings=offerings,
        unit_of_work=unit_of_work,
        public_offerings_cache=public_offerings_cache,
    )
    payload = OfferingCreate(
        title='Consulta',
        description='Atendimento inicial',
        duration_minutes=30,
        price_cents=15000,
    )

    created = await use_case.execute(payload, existing_provider.id)

    offerings.add.assert_awaited_once_with(created)
    unit_of_work.commit.assert_awaited_once_with()
    public_offerings_cache.invalidate.assert_awaited_once_with(existing_provider.id)
    unit_of_work.refresh.assert_awaited_once_with(created)
    assert created.provider_id == existing_provider.id
    assert created.title == 'Consulta'
    assert created.description == 'Atendimento inicial'
    assert created.duration_minutes == 30
    assert created.price_cents == 15000
    assert created.is_active is True
    assert 'offering.created' in {
        getattr(record, 'event_name', None) for record in caplog.records
    }


@pytest.mark.asyncio
async def test_create_offering_uses_current_provider_id_from_token() -> None:
    current_provider_id = uuid4()
    offerings = offering_repository_mock()
    unit_of_work = unit_of_work_mock()
    use_case = CreateOfferingUseCase(
        offerings=offerings,
        unit_of_work=unit_of_work,
    )
    payload = OfferingCreate(title='Consulta', duration_minutes=30)

    created = await use_case.execute(payload, current_provider_id)

    offerings.add.assert_awaited_once_with(created)
    unit_of_work.commit.assert_awaited_once_with()
    unit_of_work.refresh.assert_awaited_once_with(created)
    assert created.provider_id == current_provider_id


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
async def test_list_public_provider_offerings_returns_cached_payload() -> None:
    existing_provider = provider()
    public_cache = public_offerings_cache_mock()
    cached_offering = OfferingPublic(
        id=uuid4(),
        provider_id=existing_provider.id,
        title='Consulta',
        description='Atendimento inicial',
        duration_minutes=30,
        price_cents=15000,
        is_active=True,
    )
    public_cache.get = AsyncMock(return_value=[cached_offering])
    use_case = ListPublicProviderOfferingsUseCase(
        providers=provider_repository_mock(provider_by_slug=existing_provider),
        offerings=offering_repository_mock(),
        public_cache=public_cache,
    )

    result = await use_case.execute(existing_provider.slug)

    assert result == [cached_offering]
    public_cache.set.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_public_provider_offerings_caches_fresh_payload() -> None:
    existing_provider = provider()
    expected_offering = offering(existing_provider.id)
    public_cache = public_offerings_cache_mock()
    use_case = ListPublicProviderOfferingsUseCase(
        providers=provider_repository_mock(provider_by_slug=existing_provider),
        offerings=offering_repository_mock(active_offerings=[expected_offering]),
        public_cache=public_cache,
    )

    result = await use_case.execute(existing_provider.slug)

    assert [item.title for item in result] == ['Consulta']
    public_cache.set.assert_awaited_once()


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
    offerings = offering_repository_mock(active_offerings=[expected_offering])
    use_case = ListProviderOfferingsUseCase(
        offerings=offerings,
    )

    result = await use_case.execute(existing_provider.id)

    offerings.list_by_provider_id.assert_awaited_once_with(existing_provider.id)
    assert result == [expected_offering]


@pytest.mark.asyncio
async def test_list_provider_offerings_uses_current_provider_id_from_token() -> None:
    current_provider_id = uuid4()
    offerings = offering_repository_mock()
    use_case = ListProviderOfferingsUseCase(
        offerings=offerings,
    )

    await use_case.execute(current_provider_id)

    offerings.list_by_provider_id.assert_awaited_once_with(current_provider_id)


@pytest.mark.asyncio
async def test_update_offering_updates_only_sent_fields(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
    existing_offering = offering(uuid4())
    offerings = offering_repository_mock(offering_by_id=existing_offering)
    unit_of_work = unit_of_work_mock()
    public_offerings_cache = public_offerings_cache_mock()
    public_availability_cache = public_availability_cache_mock()
    use_case = UpdateOfferingUseCase(
        offerings=offerings,
        unit_of_work=unit_of_work,
        public_offerings_cache=public_offerings_cache,
        public_availability_cache=public_availability_cache,
    )
    payload = OfferingUpdate(title='Consulta atualizada', is_active=False)

    updated = await use_case.execute(
        existing_offering.id,
        payload,
        existing_offering.provider_id,
    )

    offerings.get_by_id.assert_awaited_once_with(existing_offering.id)
    unit_of_work.commit.assert_awaited_once_with()
    public_offerings_cache.invalidate.assert_awaited_once_with(
        existing_offering.provider_id
    )
    public_availability_cache.bump_schedule_version.assert_awaited_once_with(
        existing_offering.provider_id
    )
    unit_of_work.refresh.assert_awaited_once_with(updated)
    assert updated is existing_offering
    assert updated.title == 'Consulta atualizada'
    assert updated.is_active is False
    assert updated.description == 'Atendimento inicial'
    assert updated.duration_minutes == 30
    assert updated.price_cents == 15000
    updated_event = next(
        record
        for record in caplog.records
        if getattr(record, 'event_name', None) == 'offering.updated'
    )
    assert updated_event.__dict__['schedule_changed'] is True


@pytest.mark.asyncio
async def test_update_offering_raises_when_offering_is_missing(
    caplog: pytest.LogCaptureFixture,
) -> None:
    caplog.set_level(logging.INFO)
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
    assert caplog.records[-1].__dict__['reason'] == 'not_found'


@pytest.mark.asyncio
async def test_update_offering_raises_when_offering_is_not_owned(
    caplog: pytest.LogCaptureFixture,
) -> None:
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
    assert caplog.records[-1].__dict__['reason'] == 'access_forbidden'


@pytest.mark.asyncio
async def test_update_offering_does_not_bump_schedule_for_catalog_only_changes() -> (
    None
):
    existing_offering = offering(uuid4())
    offerings = offering_repository_mock(offering_by_id=existing_offering)
    unit_of_work = unit_of_work_mock()
    public_offerings_cache = public_offerings_cache_mock()
    public_availability_cache = public_availability_cache_mock()
    use_case = UpdateOfferingUseCase(
        offerings=offerings,
        unit_of_work=unit_of_work,
        public_offerings_cache=public_offerings_cache,
        public_availability_cache=public_availability_cache,
    )

    await use_case.execute(
        existing_offering.id,
        OfferingUpdate(title='Novo titulo'),
        existing_offering.provider_id,
    )

    public_offerings_cache.invalidate.assert_awaited_once_with(
        existing_offering.provider_id
    )
    public_availability_cache.bump_schedule_version.assert_not_awaited()
