from datetime import date, datetime
from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, status

from app.api.deps import (
    CreateAvailabilityRuleUseCaseDep,
    ListProviderAvailabilityRulesUseCaseDep,
    ListProviderAvailableSlotsUseCaseDep,
)
from app.modules.appointments.application.exceptions import (
    OfferingDoesNotBelongToProvider,
)
from app.modules.availability.infrastructure.models import AvailabilityRule
from app.modules.availability.schemas.availability_rules import (
    AvailabilityRuleCreate,
    AvailabilityRulePublic,
)
from app.modules.offerings.application.exceptions import OfferingNotFound
from app.modules.providers.application.exceptions import ProviderNotFound

availability_router = APIRouter(tags=["availability"])


@availability_router.post(
    "/providers/{provider_id}/availability-rules",
    response_model=AvailabilityRulePublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_provider_availability(
    provider_id: UUID,
    payload: AvailabilityRuleCreate,
    use_case: CreateAvailabilityRuleUseCaseDep,
) -> AvailabilityRule:
    try:
        return await use_case.execute(provider_id=provider_id, payload=payload)
    except ProviderNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider not found",
        ) from exc


@availability_router.get(
    "/providers/{provider_id}/availability-rules",
    response_model=list[AvailabilityRulePublic],
    status_code=status.HTTP_200_OK,
)
async def list_provider_availability_rules(
    provider_id: UUID,
    use_case: ListProviderAvailabilityRulesUseCaseDep,
) -> list[AvailabilityRule]:
    try:
        return await use_case.execute(provider_id)
    except ProviderNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider not found",
        ) from exc


@availability_router.get(
    "/providers/{provider_slug}/available-slots",
    response_model=list[datetime],
)
async def list_provider_available_slots(
    provider_slug: str,
    use_case: ListProviderAvailableSlotsUseCaseDep,
    offering_id: Annotated[UUID, Query()],
    target_date: Annotated[date, Query(alias="date")],
) -> list[datetime]:
    try:
        return await use_case.execute(
            provider_slug=provider_slug,
            offering_id=offering_id,
            target_date=target_date,
        )
    except ProviderNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider not found",
        ) from exc
    except OfferingNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="offering not found",
        ) from exc
    except OfferingDoesNotBelongToProvider as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="offering does not belong to provider",
        ) from exc
