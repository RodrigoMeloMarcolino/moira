from datetime import date, datetime, time
from unittest.mock import AsyncMock, Mock
from uuid import UUID, uuid4

import pytest

from app.modules.appointments.application.exceptions import (
    OfferingDoesNotBelongToProvider,
)
from app.modules.appointments.application.output_ports import AppointmentSlotRepository
from app.modules.appointments.infrastructure.models import AppointmentSlot
from app.modules.availability.application.exceptions import AvailabilityNotFound
from app.modules.availability.application.output_ports import AvailabilityRuleRepository
from app.modules.availability.application.use_cases import (
    CreateAvailabilityRuleUseCase,
    ListProviderAvailabilityRulesUseCase,
    ListProviderAvailableSlotsUseCase,
    UpdateProviderAvailabilityRuleUseCase,
)
from app.modules.availability.infrastructure.models import AvailabilityRule
from app.modules.availability.schemas.availability_rules import (
    AvailabilityRuleCreate,
    AvailabilityRuleUpdate,
)
from app.modules.offerings.application.exceptions import OfferingNotFound
from app.modules.offerings.application.output_ports import OfferingRepository
from app.modules.offerings.infrastructure.models import Offering
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


def offering(provider_id: UUID, *, duration_minutes: int = 60) -> Offering:
    return Offering(
        id=uuid4(),
        provider_id=provider_id,
        title='Consulta',
        description='Atendimento inicial',
        duration_minutes=duration_minutes,
        price_cents=15000,
        is_active=True,
    )


def availability_rule(
    provider_id: UUID,
    *,
    weekday: int = 3,
    start_time: time = time(8, 0),
    end_time: time = time(12, 0),
    is_active: bool = True,
) -> AvailabilityRule:
    return AvailabilityRule(
        id=uuid4(),
        provider_id=provider_id,
        weekday=weekday,
        start_time=start_time,
        end_time=end_time,
        is_active=is_active,
    )


def appointment_slot(provider_id: UUID, slot_start_at: datetime) -> AppointmentSlot:
    return AppointmentSlot(
        id=uuid4(),
        appointment_id=uuid4(),
        provider_id=provider_id,
        slot_start_at=slot_start_at,
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


def availability_rule_repository_mock(
    *,
    rule_by_id: AvailabilityRule | None = None,
    rules_by_provider: list[AvailabilityRule] | None = None,
    active_rules: list[AvailabilityRule] | None = None,
) -> Mock:
    rules = Mock(spec=AvailabilityRuleRepository)
    rules.add = AsyncMock()
    rules.get_by_id = AsyncMock(return_value=rule_by_id)
    rules.list_by_provider = AsyncMock(return_value=rules_by_provider or [])
    rules.list_active_by_provider_and_weekday = AsyncMock(
        return_value=active_rules or []
    )
    return rules


def offering_repository_mock(
    *,
    active_offering: Offering | None = None,
) -> Mock:
    offerings = Mock(spec=OfferingRepository)
    offerings.get_active_by_id = AsyncMock(return_value=active_offering)
    return offerings


def appointment_slot_repository_mock(
    *,
    occupied_slots: list[AppointmentSlot] | None = None,
) -> Mock:
    appointment_slots = Mock(spec=AppointmentSlotRepository)
    appointment_slots.list_by_provider_and_time_range = AsyncMock(
        return_value=occupied_slots or []
    )
    return appointment_slots


def unit_of_work_mock() -> Mock:
    unit_of_work = Mock(spec=UnitOfWork)
    unit_of_work.commit = AsyncMock()
    unit_of_work.refresh = AsyncMock()
    return unit_of_work


@pytest.mark.asyncio
async def test_create_availability_rule_creates_rule_for_existing_provider() -> None:
    existing_provider = provider()
    providers = provider_repository_mock(provider_by_id=existing_provider)
    rules = availability_rule_repository_mock()
    unit_of_work = unit_of_work_mock()
    use_case = CreateAvailabilityRuleUseCase(
        availability_rules=rules,
        providers=providers,
        uow=unit_of_work,
    )
    payload = AvailabilityRuleCreate(
        weekday=3,
        start_time=time(8, 0),
        end_time=time(12, 0),
    )

    created = await use_case.execute(
        existing_provider.id,
        payload,
        existing_provider.id,
    )

    providers.get_by_id.assert_awaited_once_with(existing_provider.id)
    rules.add.assert_awaited_once_with(created)
    unit_of_work.commit.assert_awaited_once_with()
    unit_of_work.refresh.assert_awaited_once_with(created)
    assert created.provider_id == existing_provider.id
    assert created.weekday == 3
    assert created.start_time == time(8, 0)
    assert created.end_time == time(12, 0)
    assert created.is_active is True


@pytest.mark.asyncio
async def test_create_availability_rule_raises_when_provider_is_missing() -> None:
    missing_provider_id = uuid4()
    providers = provider_repository_mock()
    rules = availability_rule_repository_mock()
    unit_of_work = unit_of_work_mock()
    use_case = CreateAvailabilityRuleUseCase(
        availability_rules=rules,
        providers=providers,
        uow=unit_of_work,
    )
    payload = AvailabilityRuleCreate(
        weekday=3,
        start_time=time(8, 0),
        end_time=time(12, 0),
    )

    with pytest.raises(ProviderNotFound):
        await use_case.execute(missing_provider_id, payload, uuid4())

    providers.get_by_id.assert_awaited_once_with(missing_provider_id)
    rules.add.assert_not_awaited()
    unit_of_work.commit.assert_not_awaited()
    unit_of_work.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_create_availability_rule_raises_when_provider_is_not_owned() -> None:
    existing_provider = provider()
    providers = provider_repository_mock(provider_by_id=existing_provider)
    rules = availability_rule_repository_mock()
    unit_of_work = unit_of_work_mock()
    use_case = CreateAvailabilityRuleUseCase(
        availability_rules=rules,
        providers=providers,
        uow=unit_of_work,
    )
    payload = AvailabilityRuleCreate(
        weekday=3,
        start_time=time(8, 0),
        end_time=time(12, 0),
    )

    with pytest.raises(ProviderAccessForbidden):
        await use_case.execute(existing_provider.id, payload, uuid4())

    rules.add.assert_not_awaited()
    unit_of_work.commit.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_provider_availability_rules_returns_rules() -> None:
    existing_provider = provider()
    expected_rule = availability_rule(existing_provider.id)
    providers = provider_repository_mock(provider_by_id=existing_provider)
    rules = availability_rule_repository_mock(rules_by_provider=[expected_rule])
    use_case = ListProviderAvailabilityRulesUseCase(
        availability_rules=rules,
        providers=providers,
    )

    result = await use_case.execute(existing_provider.id, existing_provider.id)

    providers.get_by_id.assert_awaited_once_with(existing_provider.id)
    rules.list_by_provider.assert_awaited_once_with(existing_provider.id)
    assert result == [expected_rule]


@pytest.mark.asyncio
async def test_list_availability_rules_raises_when_provider_is_missing() -> None:
    missing_provider_id = uuid4()
    providers = provider_repository_mock()
    rules = availability_rule_repository_mock()
    use_case = ListProviderAvailabilityRulesUseCase(
        availability_rules=rules,
        providers=providers,
    )

    with pytest.raises(ProviderNotFound):
        await use_case.execute(missing_provider_id, uuid4())

    providers.get_by_id.assert_awaited_once_with(missing_provider_id)
    rules.list_by_provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_availability_rules_raises_when_provider_is_not_owned() -> None:
    existing_provider = provider()
    providers = provider_repository_mock(provider_by_id=existing_provider)
    rules = availability_rule_repository_mock()
    use_case = ListProviderAvailabilityRulesUseCase(
        availability_rules=rules,
        providers=providers,
    )

    with pytest.raises(ProviderAccessForbidden):
        await use_case.execute(existing_provider.id, uuid4())

    rules.list_by_provider.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_provider_availability_rule_updates_only_sent_fields() -> None:
    existing_rule = availability_rule(uuid4())
    rules = availability_rule_repository_mock(rule_by_id=existing_rule)
    unit_of_work = unit_of_work_mock()
    use_case = UpdateProviderAvailabilityRuleUseCase(
        availability_rules=rules,
        uow=unit_of_work,
    )
    payload = AvailabilityRuleUpdate(end_time=time(13, 0), is_active=False)

    updated = await use_case.execute(
        existing_rule.id,
        payload,
        existing_rule.provider_id,
    )

    rules.get_by_id.assert_awaited_once_with(existing_rule.id)
    unit_of_work.commit.assert_awaited_once_with()
    unit_of_work.refresh.assert_awaited_once_with(updated)
    assert updated is existing_rule
    assert updated.weekday == 3
    assert updated.start_time == time(8, 0)
    assert updated.end_time == time(13, 0)
    assert updated.is_active is False


@pytest.mark.asyncio
async def test_update_provider_availability_rule_raises_when_rule_is_missing() -> None:
    missing_rule_id = uuid4()
    rules = availability_rule_repository_mock()
    unit_of_work = unit_of_work_mock()
    use_case = UpdateProviderAvailabilityRuleUseCase(
        availability_rules=rules,
        uow=unit_of_work,
    )
    payload = AvailabilityRuleUpdate(is_active=False)

    with pytest.raises(AvailabilityNotFound):
        await use_case.execute(missing_rule_id, payload, uuid4())

    rules.get_by_id.assert_awaited_once_with(missing_rule_id)
    unit_of_work.commit.assert_not_awaited()
    unit_of_work.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_update_availability_rule_raises_when_rule_is_not_owned() -> None:
    existing_rule = availability_rule(uuid4())
    rules = availability_rule_repository_mock(rule_by_id=existing_rule)
    unit_of_work = unit_of_work_mock()
    use_case = UpdateProviderAvailabilityRuleUseCase(
        availability_rules=rules,
        uow=unit_of_work,
    )
    payload = AvailabilityRuleUpdate(is_active=False)

    with pytest.raises(ProviderAccessForbidden):
        await use_case.execute(existing_rule.id, payload, uuid4())

    unit_of_work.commit.assert_not_awaited()
    unit_of_work.refresh.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_provider_available_slots_returns_free_starts_sorted() -> None:
    existing_provider = provider()
    existing_offering = offering(existing_provider.id, duration_minutes=60)
    first_rule = availability_rule(
        existing_provider.id,
        start_time=time(13, 0),
        end_time=time(14, 0),
    )
    second_rule = availability_rule(
        existing_provider.id,
        start_time=time(8, 0),
        end_time=time(9, 0),
    )
    providers = provider_repository_mock(provider_by_slug=existing_provider)
    offerings = offering_repository_mock(active_offering=existing_offering)
    rules = availability_rule_repository_mock(active_rules=[first_rule, second_rule])
    appointment_slots = appointment_slot_repository_mock()
    use_case = ListProviderAvailableSlotsUseCase(
        providers=providers,
        offerings=offerings,
        rules=rules,
        appointment_slots=appointment_slots,
    )

    result = await use_case.execute(
        provider_slug=existing_provider.slug,
        offering_id=existing_offering.id,
        target_date=date(2026, 6, 10),
    )

    assert result == [
        datetime(2026, 6, 10, 8, 0),
        datetime(2026, 6, 10, 13, 0),
    ]
    providers.get_by_slug.assert_awaited_once_with(existing_provider.slug)
    offerings.get_active_by_id.assert_awaited_once_with(existing_offering.id)
    rules.list_active_by_provider_and_weekday.assert_awaited_once_with(
        existing_provider.id,
        3,
    )
    appointment_slots.list_by_provider_and_time_range.assert_awaited_once_with(
        existing_provider.id,
        datetime(2026, 6, 10, 0, 0),
        datetime(2026, 6, 10, 23, 59, 59, 999999),
    )


@pytest.mark.asyncio
async def test_list_available_slots_removes_partially_conflicting_starts() -> None:
    existing_provider = provider()
    existing_offering = offering(existing_provider.id, duration_minutes=60)
    rule = availability_rule(
        existing_provider.id,
        start_time=time(9, 0),
        end_time=time(11, 0),
    )
    occupied = appointment_slot(
        existing_provider.id,
        datetime(2026, 6, 10, 10, 0),
    )
    use_case = ListProviderAvailableSlotsUseCase(
        providers=provider_repository_mock(provider_by_slug=existing_provider),
        offerings=offering_repository_mock(active_offering=existing_offering),
        rules=availability_rule_repository_mock(active_rules=[rule]),
        appointment_slots=appointment_slot_repository_mock(occupied_slots=[occupied]),
    )

    result = await use_case.execute(
        provider_slug=existing_provider.slug,
        offering_id=existing_offering.id,
        target_date=date(2026, 6, 10),
    )

    assert result == [datetime(2026, 6, 10, 9, 0)]


@pytest.mark.asyncio
async def test_list_available_slots_returns_empty_when_there_are_no_rules() -> None:
    existing_provider = provider()
    existing_offering = offering(existing_provider.id)
    use_case = ListProviderAvailableSlotsUseCase(
        providers=provider_repository_mock(provider_by_slug=existing_provider),
        offerings=offering_repository_mock(active_offering=existing_offering),
        rules=availability_rule_repository_mock(),
        appointment_slots=appointment_slot_repository_mock(),
    )

    result = await use_case.execute(
        provider_slug=existing_provider.slug,
        offering_id=existing_offering.id,
        target_date=date(2026, 6, 10),
    )

    assert result == []


@pytest.mark.asyncio
async def test_list_provider_available_slots_raises_when_provider_is_missing() -> None:
    offerings = offering_repository_mock()
    rules = availability_rule_repository_mock()
    appointment_slots = appointment_slot_repository_mock()
    use_case = ListProviderAvailableSlotsUseCase(
        providers=provider_repository_mock(),
        offerings=offerings,
        rules=rules,
        appointment_slots=appointment_slots,
    )

    with pytest.raises(ProviderNotFound):
        await use_case.execute(
            provider_slug='missing-provider',
            offering_id=uuid4(),
            target_date=date(2026, 6, 10),
        )

    offerings.get_active_by_id.assert_not_awaited()
    rules.list_active_by_provider_and_weekday.assert_not_awaited()
    appointment_slots.list_by_provider_and_time_range.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_provider_available_slots_raises_when_offering_is_missing() -> None:
    existing_provider = provider()
    rules = availability_rule_repository_mock()
    appointment_slots = appointment_slot_repository_mock()
    missing_offering_id = uuid4()
    use_case = ListProviderAvailableSlotsUseCase(
        providers=provider_repository_mock(provider_by_slug=existing_provider),
        offerings=offering_repository_mock(),
        rules=rules,
        appointment_slots=appointment_slots,
    )

    with pytest.raises(OfferingNotFound):
        await use_case.execute(
            provider_slug=existing_provider.slug,
            offering_id=missing_offering_id,
            target_date=date(2026, 6, 10),
        )

    rules.list_active_by_provider_and_weekday.assert_not_awaited()
    appointment_slots.list_by_provider_and_time_range.assert_not_awaited()


@pytest.mark.asyncio
async def test_list_available_slots_raises_for_other_provider_offering() -> None:
    existing_provider = provider()
    other_provider_offering = offering(uuid4())
    rules = availability_rule_repository_mock()
    appointment_slots = appointment_slot_repository_mock()
    use_case = ListProviderAvailableSlotsUseCase(
        providers=provider_repository_mock(provider_by_slug=existing_provider),
        offerings=offering_repository_mock(active_offering=other_provider_offering),
        rules=rules,
        appointment_slots=appointment_slots,
    )

    with pytest.raises(OfferingDoesNotBelongToProvider):
        await use_case.execute(
            provider_slug=existing_provider.slug,
            offering_id=other_provider_offering.id,
            target_date=date(2026, 6, 10),
        )

    rules.list_active_by_provider_and_weekday.assert_not_awaited()
    appointment_slots.list_by_provider_and_time_range.assert_not_awaited()
