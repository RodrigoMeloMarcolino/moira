from fastapi import APIRouter, HTTPException, status

from app.api.deps import GetProviderBySlugUseCaseDep, SignupProviderUseCaseDep
from app.modules.providers.application.exceptions import (
    ProviderEmailAlreadyExists,
    ProviderNotFound,
    ProviderSignupConflict,
    ProviderSlugAlreadyExists,
)
from app.modules.providers.infrastructure.models import Provider
from app.modules.providers.schemas.catalog import (
    ProviderPublic,
    ProviderSignupCreate,
)

providers_router = APIRouter(tags=["providers"])


@providers_router.post(
    "/providers/signup",
    response_model=ProviderPublic,
    status_code=status.HTTP_201_CREATED,
)
async def signup_provider_account(
    payload: ProviderSignupCreate,
    use_case: SignupProviderUseCaseDep,
) -> Provider:
    try:
        return await use_case.execute(payload)
    except ProviderEmailAlreadyExists as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="email already exists",
        ) from exc
    except ProviderSlugAlreadyExists as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="provider slug already exists",
        ) from exc
    except ProviderSignupConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="provider signup conflict",
        ) from exc


@providers_router.get("/providers/{slug}", response_model=ProviderPublic)
async def get_provider_by_slug(
    slug: str,
    use_case: GetProviderBySlugUseCaseDep,
) -> Provider:
    try:
        return await use_case.execute(slug)
    except ProviderNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="provider not found",
        ) from exc
