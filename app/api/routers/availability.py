from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Query, status

from app.api.deps import (
    CreateAvailabilityRuleUseCaseDep,
    CurrentProviderDep,
    ListProviderAvailabilityRulesUseCaseDep,
    ListPublicProviderAvailableSlotsUseCaseDep,
    UpdateProviderAvailabilityRuleUseCaseDep,
)
from app.modules.availability.infrastructure.models import AvailabilityRule
from app.modules.availability.schemas.availability_rules import (
    AvailabilityRuleCreate,
    AvailabilityRulePublic,
    AvailabilityRuleUpdate,
)

availability_router = APIRouter(tags=['availability'])


@availability_router.post(
    '/availability-rules',
    response_model=AvailabilityRulePublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_provider_availability(
    payload: AvailabilityRuleCreate,
    use_case: CreateAvailabilityRuleUseCaseDep,
    current_provider: CurrentProviderDep,
) -> AvailabilityRule:
    return await use_case.execute(
        payload=payload,
        current_provider_id=current_provider.id,
    )


@availability_router.get(
    '/availability-rules',
    response_model=list[AvailabilityRulePublic],
    status_code=status.HTTP_200_OK,
)
async def list_provider_availability_rules(
    use_case: ListProviderAvailabilityRulesUseCaseDep,
    current_provider: CurrentProviderDep,
) -> list[AvailabilityRule]:
    return await use_case.execute(current_provider.id)


@availability_router.patch(
    '/availability-rules/{rule_id}',
    response_model=AvailabilityRulePublic,
    status_code=status.HTTP_200_OK,
)
async def update_provider_availability_rule(
    rule_id: UUID,
    payload: AvailabilityRuleUpdate,
    use_case: UpdateProviderAvailabilityRuleUseCaseDep,
    current_provider: CurrentProviderDep,
) -> AvailabilityRule:
    return await use_case.execute(rule_id, payload, current_provider.id)


@availability_router.get(
    '/public/providers/{provider_slug}/available-slots',
    response_model=list[datetime],
)
async def list_provider_available_slots(
    provider_slug: str,
    use_case: ListPublicProviderAvailableSlotsUseCaseDep,
    offering_id: Annotated[UUID, Query()],
    target_date: Annotated[date, Query(alias='date')],
) -> list[datetime]:
    return await use_case.execute(
        provider_slug=provider_slug,
        offering_id=offering_id,
        target_date=target_date,
    )
