import io
import logging
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from opentelemetry.proto.collector.logs.v1.logs_service_pb2 import (
    ExportLogsServiceRequest,
)

from app.config import Settings
from app.shared.infrastructure.observability.logging.otlp import parse_otlp_headers
from app.shared.infrastructure.observability.logging.setup import configure_logging


class _Receiver(BaseHTTPRequestHandler):
    payloads: list[bytes] = []
    headers_received: list[str | None] = []

    def do_POST(self) -> None:  # noqa: N802 - required by BaseHTTPRequestHandler
        length = int(self.headers['Content-Length'])
        self.payloads.append(self.rfile.read(length))
        self.headers_received.append(self.headers.get('X-Test-Token'))
        self.send_response(200)
        self.end_headers()

    def log_message(self, format: str, *args: object) -> None:
        return None


def _any_value(value) -> object:
    field = value.WhichOneof('value')
    return getattr(value, field) if field is not None else None


def test_otlp_export_preserves_canonical_event_and_attributes(monkeypatch) -> None:
    _Receiver.payloads = []
    _Receiver.headers_received = []
    server = ThreadingHTTPServer(('127.0.0.1', 0), _Receiver)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    monkeypatch.setattr('sys.stdout', io.StringIO())

    try:
        endpoint = f'http://127.0.0.1:{server.server_port}/v1/logs'
        runtime = configure_logging(
            Settings.model_validate(
                {
                    'LOG_EXPORTERS': 'stdout,otlp',
                    'OTEL_EXPORTER_OTLP_LOGS_ENDPOINT': endpoint,
                    'OTEL_EXPORTER_OTLP_HEADERS': ('X-Test-Token=secret%20value'),
                    'OTEL_EXPORTER_OTLP_TIMEOUT': 2,
                }
            )
        )
        logging.getLogger('test.otlp').warning(
            'Cache degraded',
            extra={
                'event_name': 'cache.backend_degraded',
                'reason': 'connection_error',
                'password': 'must-not-leave-process',
            },
        )
        runtime.shutdown()
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)

    assert len(_Receiver.payloads) == 1
    request = ExportLogsServiceRequest.FromString(_Receiver.payloads[0])
    resource_logs = request.resource_logs[0]
    resource = {
        item.key: _any_value(item.value) for item in resource_logs.resource.attributes
    }
    log_record = resource_logs.scope_logs[0].log_records[0]
    attributes = {item.key: _any_value(item.value) for item in log_record.attributes}

    assert resource['service.name'] == 'moira'
    assert log_record.body.string_value == 'Cache degraded'
    assert log_record.event_name == 'cache.backend_degraded'
    assert attributes['reason'] == 'connection_error'
    assert attributes['password'] == '[REDACTED]'
    assert 'must-not-leave-process' not in _Receiver.payloads[0].decode('latin-1')
    assert _Receiver.headers_received == ['secret value']


def test_otlp_headers_are_percent_decoded() -> None:
    assert parse_otlp_headers('authorization=Bearer%20token,x-id=123') == {
        'authorization': 'Bearer token',
        'x-id': '123',
    }


def test_unavailable_otlp_endpoint_keeps_stdout_available(monkeypatch) -> None:
    output = io.StringIO()
    monkeypatch.setattr('sys.stdout', output)
    runtime = configure_logging(
        Settings.model_validate(
            {
                'LOG_EXPORTERS': 'stdout,otlp',
                'OTEL_EXPORTER_OTLP_LOGS_ENDPOINT': 'http://127.0.0.1:1/v1/logs',
                'OTEL_EXPORTER_OTLP_TIMEOUT': 0.1,
            }
        )
    )

    logging.getLogger('test.otlp').warning(
        'Remote unavailable',
        extra={'event_name': 'logging.remote_unavailable'},
    )
    runtime.shutdown()

    lines = [line for line in output.getvalue().splitlines() if line]
    assert len(lines) == 1
