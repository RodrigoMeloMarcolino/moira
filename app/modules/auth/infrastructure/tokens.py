from __future__ import annotations

import base64
import hashlib
import hmac
import json
from datetime import UTC, datetime, timedelta
from uuid import UUID

from app.modules.auth.application.exceptions import InvalidAccessToken


def _base64url_encode(value: bytes) -> str:
    return base64.urlsafe_b64encode(value).rstrip(b'=').decode('ascii')


def _base64url_decode(value: str) -> bytes:
    padding = '=' * (-len(value) % 4)
    return base64.urlsafe_b64decode(f'{value}{padding}'.encode('ascii'))


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

        self.secret_key = secret_key.encode('utf-8')
        self.algorithm = algorithm
        self.expires_delta = expires_delta

    def issue_access_token(self, *, user_id: UUID) -> str:
        now = datetime.now(tz=UTC)
        header = {'alg': self.algorithm, 'typ': 'JWT'}
        payload = {
            'sub': str(user_id),
            'iat': int(now.timestamp()),
            'exp': int((now + self.expires_delta).timestamp()),
        }

        encoded_header = _base64url_encode(
            json.dumps(header, separators=(',', ':')).encode('utf-8')
        )
        encoded_payload = _base64url_encode(
            json.dumps(payload, separators=(',', ':')).encode('utf-8')
        )
        signing_input = f'{encoded_header}.{encoded_payload}'.encode('ascii')
        signature = _base64url_encode(
            hmac.new(self.secret_key, signing_input, hashlib.sha256).digest()
        )

        return f'{encoded_header}.{encoded_payload}.{signature}'

    def verify_access_token(self, token: str) -> UUID:
        try:
            encoded_header, encoded_payload, encoded_signature = token.split('.')
            signing_input = f'{encoded_header}.{encoded_payload}'.encode('ascii')
            expected_signature = _base64url_encode(
                hmac.new(self.secret_key, signing_input, hashlib.sha256).digest()
            )

            if not hmac.compare_digest(encoded_signature, expected_signature):
                raise InvalidAccessToken

            header = json.loads(_base64url_decode(encoded_header))
            if header.get('alg') != self.algorithm or header.get('typ') != 'JWT':
                raise InvalidAccessToken

            payload = json.loads(_base64url_decode(encoded_payload))
            expires_at = int(payload['exp'])
            if datetime.now(tz=UTC).timestamp() >= expires_at:
                raise InvalidAccessToken

            return UUID(str(payload['sub']))
        except (KeyError, ValueError, json.JSONDecodeError) as exc:
            raise InvalidAccessToken from exc
