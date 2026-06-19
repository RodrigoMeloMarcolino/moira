from datetime import timedelta
from uuid import uuid4

import pytest

from app.modules.auth.application.exceptions import InvalidAccessToken
from app.modules.auth.infrastructure.tokens import HmacJwtAccessTokenCodec


def token_codec(*, expires_delta: timedelta = timedelta(minutes=30)):
    return HmacJwtAccessTokenCodec(
        secret_key='test-secret-at-least-32-bytes-long',
        algorithm='HS256',
        expires_delta=expires_delta,
    )


def test_hmac_jwt_access_token_round_trip() -> None:
    user_id = uuid4()
    token = token_codec().issue_access_token(user_id=user_id)

    assert token_codec().verify_access_token(token) == user_id


def test_hmac_jwt_access_token_rejects_invalid_signature() -> None:
    token = token_codec().issue_access_token(user_id=uuid4())
    invalid_token = f'{token[:-1]}x'

    with pytest.raises(InvalidAccessToken):
        token_codec().verify_access_token(invalid_token)


def test_hmac_jwt_access_token_rejects_expired_token() -> None:
    token = token_codec(expires_delta=timedelta(seconds=-1)).issue_access_token(
        user_id=uuid4()
    )

    with pytest.raises(InvalidAccessToken):
        token_codec().verify_access_token(token)


def test_hmac_jwt_access_token_rejects_malformed_token() -> None:
    with pytest.raises(InvalidAccessToken):
        token_codec().verify_access_token('not-a-token')
