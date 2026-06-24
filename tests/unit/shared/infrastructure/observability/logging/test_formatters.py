import json
import logging
from datetime import UTC, date, datetime
from uuid import uuid4

from app.shared.infrastructure.observability.logging.context import (
    bind_request_context,
    reset_request_context,
)
from app.shared.infrastructure.observability.logging.formatters import (
    CanonicalLogFilter,
    JsonFormatter,
)


def test_json_formatter_emits_canonical_safe_payload() -> None:
    entity_id = uuid4()
    record = logging.makeLogRecord(
        {
            'name': 'test',
            'levelno': logging.INFO,
            'levelname': 'INFO',
            'msg': 'Booking completed',
            'args': (),
            'event_name': 'appointment.booking_succeeded',
            'appointment.id': entity_id,
            'appointment.start_at': datetime(2026, 6, 23, 12, tzinfo=UTC),
            'target_date': date(2026, 6, 23),
            'password': 'never-log-me',
            'nested': {'email': 'private@example.com', 'safe': 'value'},
        }
    )
    tokens = bind_request_context('request-1', 'correlation-1')
    try:
        assert CanonicalLogFilter().filter(record)
        payload = json.loads(JsonFormatter({'service.name': 'moira'}).format(record))
    finally:
        reset_request_context(tokens)

    assert payload['severity_text'] == 'INFO'
    assert payload['severity_number'] == 9
    assert payload['event_name'] == 'appointment.booking_succeeded'
    assert payload['resource'] == {'service.name': 'moira'}
    assert payload['attributes']['appointment.id'] == str(entity_id)
    assert payload['attributes']['appointment.start_at'].endswith('Z')
    assert payload['attributes']['target_date'] == '2026-06-23'
    assert payload['attributes']['request.id'] == 'request-1'
    assert payload['attributes']['correlation.id'] == 'correlation-1'
    serialized = json.dumps(payload)
    assert 'never-log-me' not in serialized
    assert 'private@example.com' not in serialized
    assert payload['attributes']['password'] == '[REDACTED]'
    assert payload['attributes']['nested']['email'] == '[REDACTED]'


def test_exception_stack_does_not_include_exception_message() -> None:
    try:
        raise RuntimeError('secret exception message')
    except RuntimeError:
        record = logging.getLogger('test').makeRecord(
            'test',
            logging.ERROR,
            __file__,
            1,
            'Unexpected failure',
            (),
            exc_info=__import__('sys').exc_info(),
        )

    payload = json.loads(JsonFormatter({'service.name': 'moira'}).format(record))

    assert payload['attributes']['exception.type'] == 'RuntimeError'
    assert 'secret exception message' not in json.dumps(payload)
