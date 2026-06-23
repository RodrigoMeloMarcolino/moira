from uuid import UUID

from fastapi import APIRouter, HTTPException, status

from app.api.deps import (
    CreateOfferingUseCaseDep,
    CurrentProviderDep,
    ListProviderOfferingsUseCaseDep,
    ListPublicProviderOfferingsUseCaseDep,
    UpdateOfferingUseCaseDep,
)
from app.modules.offerings.application.exceptions import OfferingNotFound
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

offerings_router = APIRouter(tags=['offerings'])


@offerings_router.post(
    '/offerings',
    response_model=OfferingPublic,
    status_code=status.HTTP_201_CREATED,
)
async def create_offering(
    payload: OfferingCreate,
    use_case: CreateOfferingUseCaseDep,
    current_provider: CurrentProviderDep,
) -> Offering:
    return await use_case.execute(payload, current_provider.id)


@offerings_router.get(
    '/public/providers/{slug}/offerings',
    response_model=list[OfferingPublic],
)
async def list_active_provider_offerings(
    slug: str,
    use_case: ListPublicProviderOfferingsUseCaseDep,
) -> list[OfferingPublic]:
    try:
        return await use_case.execute(slug)
    except ProviderNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='provider not found',
        ) from exc


@offerings_router.get(
    '/offerings',
    response_model=list[OfferingPublic],
)
async def list_provider_offerings(
    use_case: ListProviderOfferingsUseCaseDep,
    current_provider: CurrentProviderDep,
) -> list[Offering]:
    return await use_case.execute(current_provider.id)


@offerings_router.patch(
    '/offerings/{offering_id}',
    response_model=OfferingPublic,
)
async def update_offering(
    offering_id: UUID,
    payload: OfferingUpdate,
    use_case: UpdateOfferingUseCaseDep,
    current_provider: CurrentProviderDep,
) -> Offering:
    try:
        return await use_case.execute(offering_id, payload, current_provider.id)
    except OfferingNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail='offering not found',
        ) from exc
    except ProviderAccessForbidden as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='provider access forbidden',
        ) from exc
