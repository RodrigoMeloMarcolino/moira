class UnitOfWorkError(Exception):
    pass


class UnitOfWorkConflict(UnitOfWorkError):
    pass
