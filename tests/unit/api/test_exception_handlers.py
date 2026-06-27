import json

import pytest
from starlette.requests import Request

from app.api.exception_handlers import application_exception_handler
from app.modules.appointments.application.exceptions import (
    AppointmentBookingConflict,
    AppointmentIdempotencyConflict,
    AppointmentStartUnavailable,
    InvalidAppointmentStart,
    OfferingDoesNotBelongToProvider,
)
from app.modules.auth.application.exceptions import (
    InvalidAccessToken,
    InvalidCredentials,
)
from app.modules.availability.application.exceptions import AvailabilityNotFound
from app.modules.offerings.application.exceptions import OfferingNotFound
from app.modules.providers.application.exceptions import (
    ProviderAccessForbidden,
    ProviderEmailAlreadyExists,
    ProviderNotFound,
    ProviderSignupConflict,
    ProviderSlugAlreadyExists,
)


def _request() -> Request:
    return Request({'type': 'http', 'headers': []})


def _response_body(response) -> dict:
    return json.loads(response.body.decode())


@pytest.mark.asyncio
@pytest.mark.parametrize(
    ('exception', 'status_code', 'code', 'message'),
    [
        (InvalidCredentials(), 401, 'invalid_credentials', 'invalid credentials'),
        (InvalidAccessToken(), 401, 'invalid_access_token', 'invalid access token'),
        (
            ProviderEmailAlreadyExists(),
            409,
            'email_already_exists',
            'email already exists',
        ),
        (
            ProviderSlugAlreadyExists(),
            409,
            'provider_slug_already_exists',
            'provider slug already exists',
        ),
        (
            ProviderSignupConflict(),
            409,
            'provider_signup_conflict',
            'provider signup conflict',
        ),
        (ProviderNotFound(), 404, 'provider_not_found', 'provider not found'),
        (
            ProviderAccessForbidden(),
            403,
            'provider_access_forbidden',
            'provider access forbidden',
        ),
        (OfferingNotFound(), 404, 'offering_not_found', 'offering not found'),
        (
            AvailabilityNotFound(),
            404,
            'availability_rule_not_found',
            'availability rule not found',
        ),
        (
            OfferingDoesNotBelongToProvider(),
            403,
            'offering_does_not_belong_to_provider',
            'offering does not belong to provider',
        ),
        (InvalidAppointmentStart(), 422, 'invalid_start_at', 'invalid start_at'),
        (
            AppointmentBookingConflict(),
            409,
            'this_time_slot_isn_t_available_anymore',
            'this time slot isn`t available anymore',
        ),
        (
            AppointmentIdempotencyConflict(),
            409,
            'idempotency_key_was_already_used_with_another_payload',
            'idempotency key was already used with another payload',
        ),
        (
            AppointmentStartUnavailable(),
            400,
            'appointment_start_at_is_outside_provider_availability',
            'appointment start_at is outside provider availability',
        ),
    ],
)
async def test_known_application_exceptions_use_stable_error_mapping(
    exception: Exception,
    status_code: int,
    code: str,
    message: str,
) -> None:
    response = await application_exception_handler(_request(), exception)

    assert response.status_code == status_code
    assert _response_body(response) == {
        'error': {
            'code': code,
            'message': message,
            'details': None,
        }
    }


@pytest.mark.asyncio
async def test_known_application_exception_code_does_not_depend_on_message() -> None:
    response = await application_exception_handler(
        _request(),
        AppointmentIdempotencyConflict('editorial text changed'),
    )

    assert response.status_code == 409
    assert _response_body(response) == {
        'error': {
            'code': 'idempotency_key_was_already_used_with_another_payload',
            'message': 'idempotency key was already used with another payload',
            'details': None,
        }
    }
