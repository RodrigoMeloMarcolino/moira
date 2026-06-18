from typing import Protocol
from uuid import UUID


class PasswordHasher(Protocol):
    def hash(self, password: str) -> str: ...

    def verify(self, password: str, password_hash: str) -> bool: ...


class AccessTokenIssuer(Protocol):
    def issue_access_token(self, *, user_id: UUID) -> str: ...


class AccessTokenVerifier(Protocol):
    def verify_access_token(self, token: str) -> UUID: ...
