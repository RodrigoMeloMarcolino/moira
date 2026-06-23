from __future__ import annotations

import json
import logging
import traceback
from collections.abc import Mapping
from datetime import UTC, date, datetime
from enum import Enum
from typing import Any
from uuid import UUID

from app.shared.infrastructure.observability.logging.context import (
    current_request_context,
)

OTLP_SEVERITY_NUMBERS = {
    logging.DEBUG: 5,
    logging.INFO: 9,
    logging.WARNING: 13,
    logging.ERROR: 17,
    logging.CRITICAL: 21,
}

LOG_RECORD_FIELDS = set(logging.makeLogRecord({}).__dict__) | {
    'message',
    'asctime',
}
CANONICAL_FIELDS = {'event_name', 'resource', 'trace_id', 'span_id'}
SENSITIVE_KEYS = {
    'password',
    'password_hash',
    'token',
    'access_token',
    'authorization',
    'cookie',
    'email',
    'phone',
    'notes',
    'idempotency_key',
    'idempotency.key',
    'database_url',
    'database.url',
    'redis_url',
    'redis.url',
    'otel_exporter_otlp_headers',
}
REDACTED = '[REDACTED]'


def _normalized_key(key: object) -> str:
    return str(key).strip().lower().replace('-', '_')


def _is_sensitive_key(key: object) -> bool:
    normalized = _normalized_key(key)
    return normalized in SENSITIVE_KEYS or normalized.rsplit('.', maxsplit=1)[-1] in {
        'password',
        'password_hash',
        'token',
        'access_token',
        'authorization',
        'cookie',
        'email',
        'phone',
        'notes',
        'idempotency_key',
        'database_url',
        'redis_url',
        'otel_exporter_otlp_headers',
    }


def safe_value(value: Any) -> Any:
    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, datetime):
        if value.tzinfo is None:
            value = value.replace(tzinfo=UTC)
        return (
            value.astimezone(UTC)
            .isoformat(timespec='milliseconds')
            .replace('+00:00', 'Z')
        )
    if isinstance(value, date):
        return value.isoformat()
    if isinstance(value, Enum):
        return safe_value(value.value)
    if isinstance(value, Mapping):
        return {
            str(key): REDACTED if _is_sensitive_key(key) else safe_value(item)
            for key, item in value.items()
        }
    if isinstance(value, (list, tuple, set, frozenset)):
        return [safe_value(item) for item in value]

    try:
        return str(value)
    except Exception:
        return f'<unserializable {type(value).__name__}>'


class CanonicalLogFilter(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        for key, value in current_request_context().items():
            record.__dict__.setdefault(key, value)

        for key in list(record.__dict__):
            if key in LOG_RECORD_FIELDS:
                continue
            if record.__dict__[key] is None:
                del record.__dict__[key]
                continue
            if _is_sensitive_key(key):
                record.__dict__[key] = REDACTED
            else:
                record.__dict__[key] = safe_value(record.__dict__[key])
        return True


def _exception_attributes(record: logging.LogRecord) -> dict[str, str]:
    if not record.exc_info or record.exc_info[0] is None:
        return {}

    exception_type, _, exception_traceback = record.exc_info
    stacktrace = '\n'.join(
        f'File {frame.filename}, line {frame.lineno}, in {frame.name}'
        for frame in traceback.extract_tb(exception_traceback)
    )
    return {
        'exception.type': exception_type.__name__,
        'exception.stacktrace': stacktrace,
    }


def record_attributes(record: logging.LogRecord) -> dict[str, Any]:
    attributes = {
        key: safe_value(value)
        for key, value in record.__dict__.items()
        if key not in LOG_RECORD_FIELDS and key not in CANONICAL_FIELDS
    }
    attributes.update(_exception_attributes(record))
    return attributes


def build_log_payload(
    record: logging.LogRecord,
    resource: Mapping[str, Any],
) -> dict[str, Any]:
    timestamp = datetime.fromtimestamp(record.created, tz=UTC)
    payload: dict[str, Any] = {
        'timestamp': timestamp.isoformat(timespec='milliseconds').replace(
            '+00:00', 'Z'
        ),
        'severity_text': record.levelname,
        'severity_number': OTLP_SEVERITY_NUMBERS.get(record.levelno, 0),
        'body': record.getMessage(),
        'event_name': getattr(record, 'event_name', 'log.message'),
        'resource': safe_value(resource),
        'attributes': record_attributes(record),
    }
    for field in ('trace_id', 'span_id'):
        value = getattr(record, field, None)
        if value:
            payload[field] = safe_value(value)
    return payload


class JsonFormatter(logging.Formatter):
    def __init__(self, resource: Mapping[str, Any]) -> None:
        super().__init__()
        self.resource = dict(resource)

    def format(self, record: logging.LogRecord) -> str:
        try:
            payload = build_log_payload(record, self.resource)
            return json.dumps(payload, ensure_ascii=False, separators=(',', ':'))
        except Exception:
            fallback = {
                'timestamp': datetime.now(UTC)
                .isoformat(timespec='milliseconds')
                .replace('+00:00', 'Z'),
                'severity_text': 'ERROR',
                'severity_number': OTLP_SEVERITY_NUMBERS[logging.ERROR],
                'body': 'log serialization failed',
                'event_name': 'logging.serialization_failed',
                'resource': safe_value(self.resource),
                'attributes': {},
            }
            return json.dumps(fallback, ensure_ascii=False, separators=(',', ':'))


class ConsoleFormatter(logging.Formatter):
    def __init__(self, resource: Mapping[str, Any]) -> None:
        super().__init__()
        self.resource = dict(resource)

    def format(self, record: logging.LogRecord) -> str:
        payload = build_log_payload(record, self.resource)
        attributes = ' '.join(
            f'{key}={value!r}' for key, value in payload['attributes'].items()
        )
        suffix = f' {attributes}' if attributes else ''
        return (
            f'{payload["timestamp"]} {payload["severity_text"]} '
            f'{payload["event_name"]} {payload["body"]}{suffix}'
        )
