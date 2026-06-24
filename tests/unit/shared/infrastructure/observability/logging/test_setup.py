import io
import json
import logging

from app.config import Settings
from app.shared.infrastructure.observability.logging.setup import (
    HANDLER_MARKER,
    configure_logging,
)


def test_configure_logging_is_idempotent(monkeypatch) -> None:
    output = io.StringIO()
    monkeypatch.setattr('sys.stdout', output)
    settings = Settings.model_validate(
        {'LOG_FORMAT': 'json', 'LOG_EXPORTERS': 'stdout'}
    )

    first = configure_logging(settings)
    second = configure_logging(settings)
    logging.getLogger('test.setup').info(
        'Configured once', extra={'event_name': 'test.configured'}
    )

    handlers = [
        handler
        for handler in logging.getLogger().handlers
        if getattr(handler, HANDLER_MARKER, False)
    ]
    assert len(handlers) == 1
    lines = [line for line in output.getvalue().splitlines() if line]
    assert len(lines) == 1
    assert json.loads(lines[0])['event_name'] == 'test.configured'
    first.shutdown()
    second.shutdown()
