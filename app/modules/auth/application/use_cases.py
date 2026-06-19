from app.modules.auth.application.exceptions import InvalidCredentials
from app.modules.auth.application.ports import AccessTokenIssuer, PasswordHasher
from app.modules.auth.schemas.login import AccessTokenPublic, LoginCreate
from app.modules.providers.application.output_ports import ProviderRepository
from app.modules.users.application.output_ports import UserRepository


class LoginProviderUseCase:
    def __init__(
        self,
        *,
        users: UserRepository,
        providers: ProviderRepository,
        password_hasher: PasswordHasher,
        access_tokens: AccessTokenIssuer,
        access_token_expires_in: int,
    ) -> None:
        self.users = users
        self.providers = providers
        self.password_hasher = password_hasher
        self.access_tokens = access_tokens
        self.access_token_expires_in = access_token_expires_in

    async def execute(self, payload: LoginCreate) -> AccessTokenPublic:
        user = await self.users.get_by_email(payload.email)
        if user is None:
            raise InvalidCredentials

        if not self.password_hasher.verify(payload.password, user.password_hash):
            raise InvalidCredentials

        provider = await self.providers.get_by_user_id(user.id)
        if provider is None:
            raise InvalidCredentials

        access_token = self.access_tokens.issue_access_token(user_id=user.id)

        return AccessTokenPublic(
            access_token=access_token,
            expires_in=self.access_token_expires_in,
            provider_id=provider.id,
        )
