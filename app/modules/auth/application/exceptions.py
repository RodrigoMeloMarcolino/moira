class AuthError(Exception):
    pass


class InvalidCredentials(AuthError):
    pass


class InvalidAccessToken(AuthError):
    pass
