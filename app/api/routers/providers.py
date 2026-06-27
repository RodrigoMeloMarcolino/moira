from fastapi import APIRouter, status

from app.api.deps import (
    GetPublicProviderBySlugUseCaseDep,
    SignupProviderUseCaseDep,
)
from app.modules.providers.infrastructure.models import Provider
from app.modules.providers.schemas.catalog import (
    ProviderCatalogPublic,
    ProviderPublic,
    ProviderSignupCreate,
)

providers_router = APIRouter(tags=['providers'])


@providers_router.post(
    '/providers/signup',
    response_model=ProviderPublic,
    status_code=status.HTTP_201_CREATED,
)
async def signup_provider_account(
    payload: ProviderSignupCreate,
    use_case: SignupProviderUseCaseDep,
) -> Provider:
    return await use_case.execute(payload)


@providers_router.get('/public/providers/{slug}', response_model=ProviderCatalogPublic)
async def get_provider_by_slug(
    slug: str,
    use_case: GetPublicProviderBySlugUseCaseDep,
) -> ProviderCatalogPublic:
    return await use_case.execute(slug)
