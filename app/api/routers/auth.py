from fastapi import APIRouter

from app.api.deps import LoginProviderUseCaseDep
from app.modules.auth.schemas.login import AccessTokenPublic, LoginCreate

auth_router = APIRouter(tags=['auth'])


@auth_router.post('/auth/login', response_model=AccessTokenPublic)
async def login_provider(
    payload: LoginCreate,
    use_case: LoginProviderUseCaseDep,
) -> AccessTokenPublic:
    return await use_case.execute(payload)
