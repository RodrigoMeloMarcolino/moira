from datetime import date, datetime, time
from uuid import UUID

from app.modules.appointments.application.exceptions import (
    OfferingDoesNotBelongToProvider,
)
from app.modules.appointments.application.output_ports import AppointmentSlotRepository
from app.modules.appointments.domain.slots import (
    build_candidate_slot_starts_for_window,
    build_occupied_slot_starts,
)
from app.modules.availability.application.exceptions import AvailabilityNotFound
from app.modules.availability.application.output_ports import AvailabilityRuleRepository
from app.modules.availability.infrastructure.models import AvailabilityRule
from app.modules.availability.schemas.availability_rules import (
    AvailabilityRuleCreate,
    AvailabilityRuleUpdate,
)
from app.modules.offerings.application.exceptions import OfferingNotFound
from app.modules.offerings.application.output_ports import OfferingRepository
from app.modules.providers.application.exceptions import (
    ProviderAccessForbidden,
    ProviderNotFound,
)
from app.modules.providers.application.output_ports import ProviderRepository
from app.shared.application.unit_of_work import UnitOfWork


class CreateAvailabilityRuleUseCase:
    def __init__(
        self,
        availability_rules: AvailabilityRuleRepository,
        providers: ProviderRepository,
        uow: UnitOfWork,
    ) -> None:
        self.availability_rules = availability_rules
        self.providers = providers
        self.uow = uow

    async def execute(
        self,
        provider_id: UUID,
        payload: AvailabilityRuleCreate,
        current_provider_id: UUID,
    ) -> AvailabilityRule:
        provider = await self.providers.get_by_id(provider_id)
        if provider is None:
            raise ProviderNotFound(f'provider not found by provider_id {provider_id}')

        if provider.id != current_provider_id:
            raise ProviderAccessForbidden('provider access forbidden')

        rule = AvailabilityRule(provider_id=provider_id, **payload.model_dump())
        await self.availability_rules.add(rule)
        await self.uow.commit()
        await self.uow.refresh(rule)

        return rule


class ListProviderAvailabilityRulesUseCase:
    def __init__(
        self,
        availability_rules: AvailabilityRuleRepository,
        providers: ProviderRepository,
    ) -> None:
        self.availability_rules = availability_rules
        self.providers = providers

    async def execute(
        self,
        provider_id: UUID,
        current_provider_id: UUID,
    ) -> list[AvailabilityRule]:
        provider = await self.providers.get_by_id(provider_id)
        if provider is None:
            raise ProviderNotFound(f'provider not found by provider_id {provider_id}')

        if provider.id != current_provider_id:
            raise ProviderAccessForbidden('provider access forbidden')

        return await self.availability_rules.list_by_provider(provider_id)


class UpdateProviderAvailabilityRuleUseCase:
    def __init__(
        self,
        availability_rules: AvailabilityRuleRepository,
        uow: UnitOfWork,
    ) -> None:
        self.availability_rules = availability_rules
        self.uow = uow

    async def execute(
        self,
        rule_id: UUID,
        payload: AvailabilityRuleUpdate,
        current_provider_id: UUID,
    ) -> AvailabilityRule:
        rule = await self.availability_rules.get_by_id(rule_id)
        if rule is None:
            raise AvailabilityNotFound(f'availability not found by rule_id {rule_id}')

        if rule.provider_id != current_provider_id:
            raise ProviderAccessForbidden('provider access forbidden')

        for field, value in payload.model_dump(exclude_unset=True).items():
            setattr(rule, field, value)

        await self.uow.commit()
        await self.uow.refresh(rule)

        return rule


class ListProviderAvailableSlotsUseCase:
    def __init__(
        self,
        providers: ProviderRepository,
        offerings: OfferingRepository,
        rules: AvailabilityRuleRepository,
        appointment_slots: AppointmentSlotRepository,
    ) -> None:
        self.providers = providers
        self.offerings = offerings
        self.availability_rules = rules
        self.appointment_slots = appointment_slots

    async def execute(
        self,
        provider_slug: str,
        offering_id: UUID,
        target_date: date,
    ) -> list[datetime]:
        provider = await self.providers.get_by_slug(provider_slug)
        if provider is None:
            raise ProviderNotFound(
                f'provider_id not found by provider_slug {provider_slug}'
            )

        offering = await self.offerings.get_active_by_id(offering_id)
        if offering is None:
            raise OfferingNotFound(f'offering not found by offering_id {offering_id}')

        if provider.id != offering.provider_id:
            raise OfferingDoesNotBelongToProvider(
                'the requested offering does not belong to this provider'
            )

        weekday = target_date.isoweekday()

        rules = await self.availability_rules.list_active_by_provider_and_weekday(
            provider.id,
            weekday,
        )

        day_start = datetime.combine(target_date, time.min)
        day_end = datetime.combine(target_date, time.max)

        occupied_slots = await self.appointment_slots.list_by_provider_and_time_range(
            provider.id,
            day_start,
            day_end,
        )

        occupied_slots_starts = {
            occupied_slot.slot_start_at for occupied_slot in occupied_slots
        }

        available_starts: list[datetime] = []

        for rule in rules:
            candidate_starts = build_candidate_slot_starts_for_window(
                date=target_date,
                duration_minutes=offering.duration_minutes,
                start_time=rule.start_time,
                end_time=rule.end_time,
            )

            for candidate_start in candidate_starts:
                required_slot_starts = build_occupied_slot_starts(
                    start_at=candidate_start,
                    duration_minutes=offering.duration_minutes,
                )

                has_conflict = any(
                    required_slot_start in occupied_slots_starts
                    for required_slot_start in required_slot_starts
                )

                if not has_conflict:
                    available_starts.append(candidate_start)

        return sorted(available_starts)
