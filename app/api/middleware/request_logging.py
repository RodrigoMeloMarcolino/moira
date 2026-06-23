from __future__ import annotations

import json
import logging
import re
import time
import traceback
from collections.abc import MutableSequence
from uuid import uuid4

from starlette.types import ASGIApp, Message, Receive, Scope, Send

from app.shared.infrastructure.observability.logging.context import (
    bind_request_context,
    reset_request_context,
)

logger = logging.getLogger(__name__)

CORRELATION_ID_PATTERN = re.compile(r'^[A-Za-z0-9._:-]{1,128}$')
REQUEST_ID_HEADER = b'x-request-id'
CORRELATION_ID_HEADER = b'x-correlation-id'


def _valid_correlation_id(value: str | None) -> str | None:
    if value is None or CORRELATION_ID_PATTERN.fullmatch(value) is None:
        return None
    return value


def _request_header(scope: Scope, name: bytes) -> str | None:
    for key, value in scope.get('headers', []):
        if key.lower() == name:
            try:
                return value.decode('ascii')
            except UnicodeDecodeError:
                return None
    return None


def _append_correlation_headers(
    headers: MutableSequence[tuple[bytes, bytes]],
    request_id: str,
    correlation_id: str,
) -> None:
    headers[:] = [
        (key, value)
        for key, value in headers
        if key.lower() not in {REQUEST_ID_HEADER, CORRELATION_ID_HEADER}
    ]
    headers.extend(
        [
            (REQUEST_ID_HEADER, request_id.encode('ascii')),
            (CORRELATION_ID_HEADER, correlation_id.encode('ascii')),
        ]
    )


def _route_template(scope: Scope) -> str:
    route = scope.get('route')
    path = getattr(route, 'path', None)
    return str(path) if path else 'unmatched'


def _duration_ms(started_at: float) -> float:
    return round((time.perf_counter() - started_at) * 1000, 3)


def _access_log_level(route: str, status_code: int) -> int:
    if route in {'/v1/health', '/v1/ready'} and status_code < 400:
        return logging.DEBUG
    return logging.INFO


class RequestLoggingMiddleware:
    def __init__(self, app: ASGIApp) -> None:
        self.app = app

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope['type'] != 'http':
            await self.app(scope, receive, send)
            return

        request_id = str(uuid4())
        correlation_id = (
            _valid_correlation_id(_request_header(scope, CORRELATION_ID_HEADER))
            or _valid_correlation_id(_request_header(scope, REQUEST_ID_HEADER))
            or request_id
        )
        context_tokens = bind_request_context(request_id, correlation_id)
        started_at = time.perf_counter()
        response_started = False
        status_code = 500

        async def send_with_context(message: Message) -> None:
            nonlocal response_started, status_code
            if message['type'] == 'http.response.start':
                response_started = True
                status_code = int(message['status'])
                headers = message.setdefault('headers', [])
                _append_correlation_headers(headers, request_id, correlation_id)
            await send(message)

        try:
            try:
                await self.app(scope, receive, send_with_context)
            except Exception as exc:
                route = _route_template(scope)
                self._log_failed(scope, route, started_at, exc)
                if response_started:
                    raise
                await self._send_internal_error(
                    send,
                    request_id=request_id,
                    correlation_id=correlation_id,
                )
                return

            route = _route_template(scope)
            logger.log(
                _access_log_level(route, status_code),
                'HTTP request completed',
                extra={
                    'event_name': 'http.request.completed',
                    'http.request.method': scope['method'],
                    'http.route': route,
                    'http.response.status_code': status_code,
                    'duration_ms': _duration_ms(started_at),
                },
            )
        finally:
            reset_request_context(context_tokens)

    def _log_failed(
        self,
        scope: Scope,
        route: str,
        started_at: float,
        exc: Exception,
    ) -> None:
        stacktrace = '\n'.join(
            f'File {frame.filename}, line {frame.lineno}, in {frame.name}'
            for frame in traceback.extract_tb(exc.__traceback__)
        )
        logger.error(
            'HTTP request failed unexpectedly',
            extra={
                'event_name': 'http.request.failed',
                'http.request.method': scope['method'],
                'http.route': route,
                'http.response.status_code': 500,
                'duration_ms': _duration_ms(started_at),
                'exception.type': type(exc).__name__,
                'exception.stacktrace': stacktrace,
            },
        )

    async def _send_internal_error(
        self,
        send: Send,
        *,
        request_id: str,
        correlation_id: str,
    ) -> None:
        body = json.dumps(
            {
                'error': {
                    'code': 'internal_server_error',
                    'message': 'internal server error',
                    'details': None,
                }
            },
            separators=(',', ':'),
        ).encode('utf-8')
        headers: list[tuple[bytes, bytes]] = [
            (b'content-type', b'application/json'),
            (b'content-length', str(len(body)).encode('ascii')),
        ]
        _append_correlation_headers(headers, request_id, correlation_id)
        await send(
            {
                'type': 'http.response.start',
                'status': 500,
                'headers': headers,
            }
        )
        await send({'type': 'http.response.body', 'body': body})
