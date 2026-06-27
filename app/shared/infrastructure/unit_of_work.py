from sqlalchemy.exc import IntegrityError
from sqlalchemy.ext.asyncio import AsyncSession

from app.shared.application.exceptions import (
    UnitOfWorkConflict,
    UnitOfWorkConflictCategory,
)

_CONSTRAINT_CATEGORIES = {
    'uq_customers_phone': UnitOfWorkConflictCategory.CUSTOMER_PHONE_UNIQUE,
    'uq_appointment_slots_provider_slot_start': (
        UnitOfWorkConflictCategory.APPOINTMENT_SLOT_UNIQUE
    ),
    'uq_appointments_provider_idempotency_key': (
        UnitOfWorkConflictCategory.APPOINTMENT_IDEMPOTENCY_KEY_UNIQUE
    ),
}


class SqlAlchemyUnitOfWork:
    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def flush(self) -> None:
        try:
            await self.session.flush()
        except IntegrityError as exc:
            raise _build_unit_of_work_conflict(exc) from exc

    async def commit(self) -> None:
        try:
            await self.session.commit()
        except IntegrityError as exc:
            raise _build_unit_of_work_conflict(exc) from exc

    async def rollback(self) -> None:
        await self.session.rollback()

    async def refresh(self, entity: object) -> None:
        await self.session.refresh(entity)


def _build_unit_of_work_conflict(exc: IntegrityError) -> UnitOfWorkConflict:
    constraint_name = _extract_constraint_name(exc)
    sqlstate = _extract_sqlstate(exc)
    reason = 'unique_violation' if sqlstate == '23505' else 'integrity_error'
    category = (
        _CONSTRAINT_CATEGORIES.get(constraint_name)
        if constraint_name is not None
        else None
    ) or UnitOfWorkConflictCategory.UNKNOWN_INTEGRITY

    return UnitOfWorkConflict(
        reason=reason,
        category=category,
        constraint_name=constraint_name,
    )


def _extract_constraint_name(exc: IntegrityError) -> str | None:
    for candidate in _iter_integrity_error_candidates(exc):
        constraint_name = getattr(candidate, 'constraint_name', None)
        if constraint_name:
            return str(constraint_name)

        diag = getattr(candidate, 'diag', None)
        constraint_name = getattr(diag, 'constraint_name', None)
        if constraint_name:
            return str(constraint_name)

    return None


def _extract_sqlstate(exc: IntegrityError) -> str | None:
    for candidate in _iter_integrity_error_candidates(exc):
        sqlstate = getattr(candidate, 'sqlstate', None) or getattr(
            candidate,
            'pgcode',
            None,
        )
        if sqlstate:
            return str(sqlstate)

    return None


def _iter_integrity_error_candidates(exc: IntegrityError) -> tuple[object, ...]:
    orig = getattr(exc, 'orig', None)
    return (
        exc,
        orig,
        getattr(orig, 'orig', None),
        getattr(orig, '__cause__', None),
        getattr(exc, '__cause__', None),
    )
