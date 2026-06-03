MIN_SIGNUP_PASSWORD_LENGTH = 8
MAX_SIGNUP_PASSWORD_LENGTH = 64


class SignupPasswordPolicyError(ValueError):
    pass


def validate_signup_password(password: str) -> None:
    password_length = len(password)

    if password_length < MIN_SIGNUP_PASSWORD_LENGTH:
        raise SignupPasswordPolicyError(
            "signup password must have at least "
            f"{MIN_SIGNUP_PASSWORD_LENGTH} characters"
        )

    if password_length > MAX_SIGNUP_PASSWORD_LENGTH:
        raise SignupPasswordPolicyError(
            f"signup password must have at most {MAX_SIGNUP_PASSWORD_LENGTH} characters"
        )
