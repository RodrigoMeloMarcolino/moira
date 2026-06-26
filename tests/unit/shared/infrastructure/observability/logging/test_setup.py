import io
import json
import logging
import warnings

from app.config import Settings
from app.main import create_app
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


def test_runtime_shutdown_is_idempotent(monkeypatch) -> None:
    output = io.StringIO()
    monkeypatch.setattr('sys.stdout', output)
    runtime = configure_logging(
        Settings.model_validate({'LOG_FORMAT': 'json', 'LOG_EXPORTERS': 'stdout'})
    )

    runtime.shutdown()
    runtime.shutdown()

    handlers = [
        handler
        for handler in logging.getLogger().handlers
        if getattr(handler, HANDLER_MARKER, False)
    ]
    assert handlers == []


def test_shutting_down_one_app_does_not_close_newer_app_logging(monkeypatch) -> None:
    output = io.StringIO()
    monkeypatch.setattr('sys.stdout', output)

    first_app = create_app()
    second_app = create_app()

    first_app.state.logging_runtime.shutdown()
    logging.getLogger('test.setup').info(
        'Still configured', extra={'event_name': 'test.still_configured'}
    )

    handlers = [
        handler
        for handler in logging.getLogger().handlers
        if getattr(handler, HANDLER_MARKER, False)
    ]
    lines = [line for line in output.getvalue().splitlines() if line]

    assert len(handlers) == 1
    assert len(lines) == 1
    assert json.loads(lines[0])['event_name'] == 'test.still_configured'

    second_app.state.logging_runtime.shutdown()


def test_otlp_configuration_does_not_emit_deprecation_warning(monkeypatch) -> None:
    output = io.StringIO()
    monkeypatch.setattr('sys.stdout', output)

    with warnings.catch_warnings(record=True) as captured:
        warnings.simplefilter('always', DeprecationWarning)
        runtime = configure_logging(
            Settings.model_validate(
                {
                    'LOG_EXPORTERS': 'stdout,otlp',
                    'OTEL_EXPORTER_OTLP_LOGS_ENDPOINT': 'http://127.0.0.1:4318/v1/logs',
                }
            )
        )
        runtime.shutdown()

    messages = [str(warning.message) for warning in captured]
    assert not any('LoggingHandler' in message for message in messages)
