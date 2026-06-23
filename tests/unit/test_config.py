import pytest
from pydantic import ValidationError

from app.config import Settings


def test_sessings_defaults() -> None:
    settings = Settings()

    assert settings.app_name == 'moira'
    assert settings.app_debug
    assert settings.database_url.startswith('postgresql+asyncpg://')
    assert settings.default_timezone == 'America/Fortaleza'
    assert settings.log_level == 'INFO'
    assert settings.log_format == 'json'
    assert settings.log_exporters == ('stdout',)


def test_logging_settings_are_normalized() -> None:
    settings = Settings.model_validate(
        {
            'LOG_LEVEL': 'debug',
            'LOG_FORMAT': 'CONSOLE',
            'LOG_EXPORTERS': 'stdout,otlp',
            'OTEL_EXPORTER_OTLP_LOGS_ENDPOINT': ('http://collector:4318/v1/logs'),
        }
    )

    assert settings.log_level == 'DEBUG'
    assert settings.log_format == 'console'
    assert settings.log_exporters == ('stdout', 'otlp')


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('LOG_LEVEL', 'verbose'),
        ('LOG_FORMAT', 'xml'),
        ('LOG_EXPORTERS', 'otlp'),
        ('LOG_EXPORTERS', 'stdout,loki'),
    ],
)
def test_invalid_logging_settings_fail(field: str, value: str) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({field: value})


def test_otlp_requires_endpoint() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({'LOG_EXPORTERS': 'stdout,otlp'})
