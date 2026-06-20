from typing import Annotated, Optional

from fastapi import APIRouter, Header, HTTPException, status

from app.api.deps import (
    BookPublicAppointmentUseCaseDep,
    CurrentProviderDep,
    ListProviderAppointmentsUseCaseDep,
)
from app.modules.appointments.application.exceptions import (
    AppointmentBookingConflict,
    AppointmentIdempotencyConflict,
    AppointmentStartUnavailable,
    InvalidAppointmentStart,
    OfferingDoesNotBelongToProvider,
)
from app.modules.appointments.infrastructure.models import Appointment
from app.modules.appointments.schemas.booking import (
    AppointmentPublic,
    PublicAppointmentBookingCreate,
)
from app.modules.offerings.application.exceptions import OfferingNotFound
from app.modules.providers.application.exceptions import ProviderNotFound

appointments_router = APIRouter(tags=['appointments'])


@appointments_router.post(
    '/public/providers/{provider_slug}/appointments',
    response_model=AppointmentPublic,
    status_code=status.HTTP_201_CREATED,
)
async def book_public_appointment(
    provider_slug: str,
    payload: PublicAppointmentBookingCreate,
    use_case: BookPublicAppointmentUseCaseDep,
    idempotency_key: Annotated[Optional[str], Header(alias='Idempotency-Key')] = None,
):
    try:
        return await use_case.execute(provider_slug, payload, idempotency_key)
    except OfferingNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='offering not found'
        ) from exc
    except ProviderNotFound as exc:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail='provider not found'
        ) from exc
    except OfferingDoesNotBelongToProvider as exc:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail='offering does not belong to provider',
        ) from exc
    except InvalidAppointmentStart as exc:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_CONTENT, detail='invalid start_at'
        ) from exc
    except AppointmentBookingConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='this time slot isn`t available anymore',
        ) from exc
    except AppointmentIdempotencyConflict as exc:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail='idempotency key was already used with another payload',
        ) from exc
    except AppointmentStartUnavailable as exc:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail='appointment start_at is outside provider availability',
        ) from exc


@appointments_router.get(
    '/appointments',
    response_model=list[AppointmentPublic],
)
async def list_provider_appointments(
    use_case: ListProviderAppointmentsUseCaseDep,
    current_provider: CurrentProviderDep,
) -> list[Appointment]:
    return await use_case.execute(current_provider.id)
