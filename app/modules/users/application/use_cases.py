from app.modules.auth.application.ports import PasswordHasher
from app.modules.users.application.exceptions import UserEmailAlreadyExists
from app.modules.users.application.output_ports import UserRepository
from app.modules.users.infrastructure.models import User


class CreateUserUseCase:
    def __init__(
        self,
        users: UserRepository,
        password_hasher: PasswordHasher,
    ) -> None:
        self.users = users
        self.password_hasher = password_hasher

    async def execute(self, *, email: str, password: str) -> User:
        existing_email = await self.users.find_id_by_email(email)
        if existing_email is not None:
            raise UserEmailAlreadyExists

        user = User(
            email=email,
            password_hash=self.password_hasher.hash(password),
        )
        await self.users.add(user)
        return user
