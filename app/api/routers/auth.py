from fastapi import APIRouter, HTTPException, status

from app.api.deps import LoginProviderUseCaseDep
from app.modules.auth.application.exceptions import InvalidCredentials
from app.modules.auth.schemas.login import AccessTokenPublic, LoginCreate

auth_router = APIRouter(tags=['auth'])


@auth_router.post('/auth/login', response_model=AccessTokenPublic)
async def login_provider(
    payload: LoginCreate,
    use_case: LoginProviderUseCaseDep,
) -> AccessTokenPublic:
    try:
        return await use_case.execute(payload)
    except InvalidCredentials as exc:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail='invalid credentials',
        ) from exc
