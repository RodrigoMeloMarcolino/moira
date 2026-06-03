class ProviderError(Exception):
    pass


class ProviderEmailAlreadyExists(ProviderError):
    pass


class ProviderSlugAlreadyExists(ProviderError):
    pass


class ProviderSignupConflict(ProviderError):
    pass


class ProviderNotFound(ProviderError):
    pass
