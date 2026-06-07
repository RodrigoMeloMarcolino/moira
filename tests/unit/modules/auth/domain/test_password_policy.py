import pytest

from app.modules.auth.domain.password_policy import (
    SignupPasswordPolicyError,
    validate_signup_password,
)


def test_signup_password_accepts_minimum_length() -> None:
    validate_signup_password("a" * 8)


def test_signup_password_accepts_maximum_length() -> None:
    validate_signup_password("a" * 64)


def test_signup_password_rejects_short_password() -> None:
    with pytest.raises(SignupPasswordPolicyError):
        validate_signup_password("a" * 7)


def test_signup_password_rejects_long_password() -> None:
    with pytest.raises(SignupPasswordPolicyError):
        validate_signup_password("a" * 65)
