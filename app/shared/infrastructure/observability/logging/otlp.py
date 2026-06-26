from urllib.parse import unquote

from opentelemetry.exporter.otlp.proto.http._log_exporter import OTLPLogExporter
from opentelemetry.instrumentation.logging.handler import LoggingHandler
from opentelemetry.sdk._logs import LoggerProvider
from opentelemetry.sdk._logs.export import BatchLogRecordProcessor
from opentelemetry.sdk.resources import Resource


class CanonicalOTLPLoggingHandler(LoggingHandler):
    def _translate(self, record):
        translated = super()._translate(record)
        translated.event_name = str(getattr(record, 'event_name', 'log.message'))
        if translated.attributes is not None:
            attributes = dict(translated.attributes)
            attributes.pop('event_name', None)
            translated.attributes = attributes
        return translated


def parse_otlp_headers(value: str | None) -> dict[str, str] | None:
    if not value:
        return None

    headers: dict[str, str] = {}
    for item in value.split(','):
        name, separator, header_value = item.partition('=')
        if not separator or not name.strip():
            raise ValueError('OTEL_EXPORTER_OTLP_HEADERS contains an invalid header')
        headers[unquote(name.strip())] = unquote(header_value.strip())
    return headers


def build_otlp_handler(
    *,
    resource_attributes: dict[str, str],
    endpoint: str,
    headers: str | None,
    timeout_seconds: float,
    level: int,
) -> tuple[CanonicalOTLPLoggingHandler, LoggerProvider]:
    provider = LoggerProvider(
        resource=Resource.create(resource_attributes),
        shutdown_on_exit=False,
    )
    exporter = OTLPLogExporter(
        endpoint=endpoint,
        headers=parse_otlp_headers(headers),
        timeout=timeout_seconds,
    )
    provider.add_log_record_processor(
        BatchLogRecordProcessor(
            exporter,
            max_queue_size=2048,
            max_export_batch_size=512,
            schedule_delay_millis=5000,
            export_timeout_millis=timeout_seconds * 1000,
        )
    )
    return CanonicalOTLPLoggingHandler(level=level, logger_provider=provider), provider
