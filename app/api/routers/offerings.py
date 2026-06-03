from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import (
    CreateOfferingUseCaseDep,
    ListActiveProviderOfferingsUseCaseDep,
    UpdateOfferingUseCaseDep,
)
from app.modules.offerings.application.exceptions import OfferingNotFound
from app.modules.offerings.infrastructure.models import Offering
from app.modules.offerings.schemas.catalog import (
    OfferingCreate,
    OfferingPublic,
    OfferingUpdate,
)
from app.modules.providers.application.exceptions import ProviderNotFound

offerings_router = APIRouter(tags=["offerings"])


@offerings_router.post(
    "/providers/{provider_id}/offerings",
    response_model=OfferingPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_offering(
    provider_id: UUID,
    payload: OfferingCreate,
    use_case: CreateOfferingUseCaseDep,
) -> Offering:
    try:
        return await use_case.execute(provider_id, payload)
    except ProviderNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider not found",
        ) from exc


@offerings_router.get(
    "/providers/{slug}/offerings",
    response_model=list[OfferingPublic],
)
async def list_active_provider_offerings(
    slug: str,
    use_case: ListActiveProviderOfferingsUseCaseDep,
) -> list[Offering]:
    try:
        return await use_case.execute(slug)
    except ProviderNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider not found",
        ) from exc


@offerings_router.patch(
    "/offerings/{offering_id}",
    response_model=OfferingPublic,
)
async def update_offering(
    offering_id: UUID,
    payload: OfferingUpdate,
    use_case: UpdateOfferingUseCaseDep,
) -> Offering:
    try:
        return await use_case.execute(offering_id, payload)
    except OfferingNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="offering not found",
        ) from exc
