from __future__ import annotations

import importlib.metadata
import logging
import sys
import threading
from dataclasses import dataclass

from opentelemetry.sdk._logs import LoggerProvider

from app.config import Settings
from app.shared.infrastructure.observability.logging.formatters import (
    CanonicalLogFilter,
    ConsoleFormatter,
    JsonFormatter,
)
from app.shared.infrastructure.observability.logging.otlp import build_otlp_handler

HANDLER_MARKER = '_moira_logging_handler'


@dataclass
class LoggingRuntime:
    provider: LoggerProvider | None = None
    shutdown_timeout_millis: int = 5000
    handlers: tuple[logging.Handler, ...] = ()
    _shutdown: bool = False

    def shutdown(self) -> None:
        if self._shutdown:
            return
        self._shutdown = True

        root_logger = logging.getLogger()
        for handler in self.handlers:
            if handler in root_logger.handlers:
                root_logger.removeHandler(handler)
            handler.close()
        self.handlers = ()

        if self.provider is None:
            return
        provider = self.provider
        self.provider = None
        provider.force_flush(timeout_millis=self.shutdown_timeout_millis)
        shutdown_thread = threading.Thread(target=provider.shutdown, daemon=True)
        shutdown_thread.start()
        shutdown_thread.join(self.shutdown_timeout_millis / 1000)


class ExcludeOpenTelemetryInternalLogs(logging.Filter):
    def filter(self, record: logging.LogRecord) -> bool:
        return not record.name.startswith('opentelemetry.')


def _service_version() -> str:
    try:
        return importlib.metadata.version('moira')
    except importlib.metadata.PackageNotFoundError:
        return 'unknown'


def resource_attributes(settings: Settings) -> dict[str, str]:
    return {
        'service.name': settings.otel_service_name or settings.app_name,
        'service.namespace': 'moira',
        'service.version': _service_version(),
        'deployment.environment.name': settings.app_env,
    }


def _detach_existing_handlers(logger: logging.Logger) -> None:
    for handler in list(logger.handlers):
        if getattr(handler, HANDLER_MARKER, False):
            logger.removeHandler(handler)


def configure_logging(settings: Settings) -> LoggingRuntime:
    level = getattr(logging, settings.log_level)
    attributes = resource_attributes(settings)
    root_logger = logging.getLogger()
    root_logger.setLevel(level)
    _detach_existing_handlers(root_logger)

    context_filter = CanonicalLogFilter()
    stdout_handler = logging.StreamHandler(sys.stdout)
    stdout_handler.setLevel(level)
    stdout_handler.addFilter(context_filter)
    stdout_handler.setFormatter(
        JsonFormatter(attributes)
        if settings.log_format == 'json'
        else ConsoleFormatter(attributes)
    )
    setattr(stdout_handler, HANDLER_MARKER, True)
    root_logger.addHandler(stdout_handler)
    handlers: list[logging.Handler] = [stdout_handler]

    provider: LoggerProvider | None = None
    if 'otlp' in settings.log_exporters:
        endpoint = settings.otel_exporter_otlp_logs_endpoint
        if endpoint is None:  # protected by Settings validation
            raise ValueError('OTLP logs endpoint is required')
        secret_headers = settings.otel_exporter_otlp_headers
        otlp_handler, provider = build_otlp_handler(
            resource_attributes=attributes,
            endpoint=str(endpoint),
            headers=(
                secret_headers.get_secret_value()
                if secret_headers is not None
                else None
            ),
            timeout_seconds=settings.otel_exporter_otlp_timeout,
            level=level,
        )
        otlp_handler.addFilter(context_filter)
        otlp_handler.addFilter(ExcludeOpenTelemetryInternalLogs())
        setattr(otlp_handler, HANDLER_MARKER, True)
        root_logger.addHandler(otlp_handler)
        handlers.append(otlp_handler)

    uvicorn_access = logging.getLogger('uvicorn.access')
    uvicorn_access.handlers.clear()
    uvicorn_access.propagate = False
    uvicorn_access.disabled = True

    uvicorn_error = logging.getLogger('uvicorn.error')
    uvicorn_error.handlers.clear()
    uvicorn_error.propagate = True
    uvicorn_error.disabled = False

    return LoggingRuntime(
        provider=provider,
        shutdown_timeout_millis=int(settings.otel_exporter_otlp_timeout * 1000),
        handlers=tuple(handlers),
    )
