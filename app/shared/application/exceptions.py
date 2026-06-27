class UnitOfWorkError(Exception):
    pass


class UnitOfWorkConflictCategory:
    CUSTOMER_PHONE_UNIQUE = 'customer_phone_unique'
    APPOINTMENT_SLOT_UNIQUE = 'appointment_slot_unique'
    APPOINTMENT_IDEMPOTENCY_KEY_UNIQUE = 'appointment_idempotency_key_unique'
    UNKNOWN_INTEGRITY = 'unknown_integrity'


class UnitOfWorkConflict(UnitOfWorkError):
    def __init__(
        self,
        message: str = 'unit of work integrity conflict',
        *,
        reason: str = 'integrity_error',
        category: str = UnitOfWorkConflictCategory.UNKNOWN_INTEGRITY,
        constraint_name: str | None = None,
    ) -> None:
        super().__init__(message)
        self.reason = reason
        self.category = category
        self.constraint_name = constraint_name
