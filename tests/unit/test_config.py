import pytest
from pydantic import ValidationError

from app.config import MAX_CACHE_TTL_SECONDS, Settings


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


def test_redis_url_is_sensitive() -> None:
    settings = Settings.model_validate(
        {'REDIS_URL': 'redis://:secret@localhost:6379/0'}
    )

    assert settings.redis_url.get_secret_value() == ('redis://:secret@localhost:6379/0')
    assert str(settings.redis_url) == '**********'


def test_default_timezone_must_be_iana_timezone() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({'DEFAULT_TIMEZONE': 'Fortaleza'})


def test_non_local_environment_rejects_default_jwt_secret() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate(
            {
                'APP_ENV': 'production',
                'JWT_SECRET_KEY': 'change-me-in-local-dev-secret-at-least-32-bytes',
            }
        )


def test_non_local_environment_rejects_weak_jwt_secret() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate(
            {'APP_ENV': 'production', 'JWT_SECRET_KEY': 'short-secret'}
        )


def test_non_local_environment_accepts_strong_jwt_secret() -> None:
    settings = Settings.model_validate(
        {
            'APP_ENV': 'production',
            'JWT_SECRET_KEY': 'a-production-secret-with-at-least-32-bytes',
        }
    )

    assert settings.app_env == 'production'


def test_jwt_algorithm_must_match_supported_codec_allowlist() -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({'JWT_ALGORITHM': 'RS256'})


@pytest.mark.parametrize(
    ('field', 'value'),
    [
        ('JWT_ACCESS_TOKEN_EXPIRE_MINUTES', 0),
        ('JWT_ACCESS_TOKEN_EXPIRE_MINUTES', 1441),
        ('OTEL_EXPORTER_OTLP_TIMEOUT', 0),
        ('OTEL_EXPORTER_OTLP_TIMEOUT', 61),
        ('CACHE_TTL_PUBLIC_PROVIDER_SECONDS', 0),
        ('CACHE_TTL_PUBLIC_PROVIDER_SECONDS', MAX_CACHE_TTL_SECONDS + 1),
        ('CACHE_TTL_PUBLIC_OFFERINGS_SECONDS', 0),
        ('CACHE_TTL_AVAILABLE_SLOTS_SECONDS', 0),
    ],
)
def test_runtime_numeric_limits_are_positive_and_bounded(
    field: str,
    value: int | float,
) -> None:
    with pytest.raises(ValidationError):
        Settings.model_validate({field: value})


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


def test_otlp_requires_endpoint(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setitem(Settings.model_config, 'env_file', None)
    monkeypatch.delenv('OTEL_EXPORTER_OTLP_LOGS_ENDPOINT', raising=False)

    with pytest.raises(ValidationError):
        Settings.model_validate({'LOG_EXPORTERS': 'stdout,otlp'})
