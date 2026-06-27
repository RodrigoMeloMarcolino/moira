import re
from collections.abc import Mapping
from dataclasses import dataclass
from typing import Any

from fastapi import FastAPI, Request, status
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

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

ERROR_CODE_PATTERN = re.compile(r'[^a-z0-9]+')


@dataclass(frozen=True)
class ErrorMapping:
    status_code: int
    code: str
    message: str
    details: Any = None


APPLICATION_ERROR_MAPPINGS: Mapping[type[Exception], ErrorMapping] = {
    InvalidCredentials: ErrorMapping(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code='invalid_credentials',
        message='invalid credentials',
    ),
    InvalidAccessToken: ErrorMapping(
        status_code=status.HTTP_401_UNAUTHORIZED,
        code='invalid_access_token',
        message='invalid access token',
    ),
    ProviderEmailAlreadyExists: ErrorMapping(
        status_code=status.HTTP_409_CONFLICT,
        code='email_already_exists',
        message='email already exists',
    ),
    ProviderSlugAlreadyExists: ErrorMapping(
        status_code=status.HTTP_409_CONFLICT,
        code='provider_slug_already_exists',
        message='provider slug already exists',
    ),
    ProviderSignupConflict: ErrorMapping(
        status_code=status.HTTP_409_CONFLICT,
        code='provider_signup_conflict',
        message='provider signup conflict',
    ),
    ProviderNotFound: ErrorMapping(
        status_code=status.HTTP_404_NOT_FOUND,
        code='provider_not_found',
        message='provider not found',
    ),
    ProviderAccessForbidden: ErrorMapping(
        status_code=status.HTTP_403_FORBIDDEN,
        code='provider_access_forbidden',
        message='provider access forbidden',
    ),
    OfferingNotFound: ErrorMapping(
        status_code=status.HTTP_404_NOT_FOUND,
        code='offering_not_found',
        message='offering not found',
    ),
    AvailabilityNotFound: ErrorMapping(
        status_code=status.HTTP_404_NOT_FOUND,
        code='availability_rule_not_found',
        message='availability rule not found',
    ),
    OfferingDoesNotBelongToProvider: ErrorMapping(
        status_code=status.HTTP_403_FORBIDDEN,
        code='offering_does_not_belong_to_provider',
        message='offering does not belong to provider',
    ),
    InvalidAppointmentStart: ErrorMapping(
        status_code=status.HTTP_422_UNPROCESSABLE_CONTENT,
        code='invalid_start_at',
        message='invalid start_at',
    ),
    AppointmentBookingConflict: ErrorMapping(
        status_code=status.HTTP_409_CONFLICT,
        code='this_time_slot_isn_t_available_anymore',
        message='this time slot isn`t available anymore',
    ),
    AppointmentIdempotencyConflict: ErrorMapping(
        status_code=status.HTTP_409_CONFLICT,
        code='idempotency_key_was_already_used_with_another_payload',
        message='idempotency key was already used with another payload',
    ),
    AppointmentStartUnavailable: ErrorMapping(
        status_code=status.HTTP_400_BAD_REQUEST,
        code='appointment_start_at_is_outside_provider_availability',
        message='appointment start_at is outside provider availability',
    ),
}


def _error_code_from_message(message: str) -> str:
    code = ERROR_CODE_PATTERN.sub('_', message.lower()).strip('_')
    return code or 'http_error'


def _error_response(
    *,
    status_code: int,
    code: str,
    message: str,
    details: Any = None,
) -> JSONResponse:
    return JSONResponse(
        status_code=status_code,
        content={
            'error': {
                'code': code,
                'message': message,
                'details': jsonable_encoder(details),
            }
        },
    )


async def application_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    error_mapping = APPLICATION_ERROR_MAPPINGS.get(type(exc))
    if error_mapping is None:
        raise exc

    return _error_response(
        status_code=error_mapping.status_code,
        code=error_mapping.code,
        message=error_mapping.message,
        details=error_mapping.details,
    )


async def http_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    if not isinstance(exc, StarletteHTTPException):
        raise exc

    detail = exc.detail
    if isinstance(detail, dict):
        message = str(detail.get('message') or detail.get('detail') or 'http error')
        code = str(detail.get('code') or _error_code_from_message(message))
        details = detail.get('details')
    else:
        message = str(detail or 'http error')
        code = _error_code_from_message(message)
        details = None

    return _error_response(
        status_code=exc.status_code,
        code=code,
        message=message,
        details=details,
    )


async def validation_exception_handler(
    request: Request,
    exc: Exception,
) -> JSONResponse:
    if not isinstance(exc, RequestValidationError):
        raise exc

    return _error_response(
        status_code=422,
        code='validation_error',
        message='request validation failed',
        details=exc.errors(),
    )


def register_exception_handlers(app: FastAPI) -> None:
    for exception_class in APPLICATION_ERROR_MAPPINGS:
        app.add_exception_handler(exception_class, application_exception_handler)
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
