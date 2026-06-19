from __future__ import annotations

from datetime import UTC, datetime, timedelta
from uuid import UUID

import jwt

from app.modules.auth.application.exceptions import InvalidAccessToken


class HmacJwtAccessTokenCodec:
    def __init__(
        self,
        *,
        secret_key: str,
        algorithm: str,
        expires_delta: timedelta,
    ) -> None:
        if algorithm != 'HS256':
            raise ValueError('only HS256 is supported')

        self.secret_key = secret_key
        self.algorithm = algorithm
        self.expires_delta = expires_delta

    def issue_access_token(self, *, user_id: UUID) -> str:
        now = datetime.now(tz=UTC)
        payload = {
            'sub': str(user_id),
            'iat': now,
            'exp': now + self.expires_delta,
        }

        return jwt.encode(
            payload,
            self.secret_key,
            algorithm=self.algorithm,
        )

    def verify_access_token(self, token: str) -> UUID:
        try:
            payload = jwt.decode(
                token,
                self.secret_key,
                algorithms=[self.algorithm],
                options={'require': ['sub', 'exp']},
            )
            return UUID(str(payload['sub']))
        except (jwt.InvalidTokenError, KeyError, ValueError) as exc:
            raise InvalidAccessToken from exc
