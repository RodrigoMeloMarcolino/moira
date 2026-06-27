from typing import Annotated, Optional

from fastapi import APIRouter, Header, status

from app.api.deps import (
    BookPublicAppointmentUseCaseDep,
    CurrentProviderDep,
    ListProviderAppointmentsUseCaseDep,
)
from app.modules.appointments.infrastructure.models import Appointment
from app.modules.appointments.schemas.booking import (
    AppointmentPublic,
    PublicAppointmentBookingCreate,
)

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
    idempotency_key: Annotated[
        Optional[str],
        Header(
            alias='Idempotency-Key',
            min_length=1,
            max_length=128,
            pattern=r'^[A-Za-z0-9._:-]+$',
        ),
    ] = None,
):
    return await use_case.execute(provider_slug, payload, idempotency_key)


@appointments_router.get(
    '/appointments',
    response_model=list[AppointmentPublic],
)
async def list_provider_appointments(
    use_case: ListProviderAppointmentsUseCaseDep,
    current_provider: CurrentProviderDep,
) -> list[Appointment]:
    return await use_case.execute(current_provider.id)
