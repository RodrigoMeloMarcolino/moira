import re
from typing import Any

from fastapi import FastAPI, Request
from fastapi.encoders import jsonable_encoder
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

ERROR_CODE_PATTERN = re.compile(r'[^a-z0-9]+')


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
    app.add_exception_handler(StarletteHTTPException, http_exception_handler)
    app.add_exception_handler(RequestValidationError, validation_exception_handler)
