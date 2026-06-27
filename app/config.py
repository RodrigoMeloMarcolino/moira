from functools import lru_cache
from typing import Annotated, Literal
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

from pydantic import AnyHttpUrl, Field, SecretStr, field_validator, model_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict

DEFAULT_LOCAL_JWT_SECRET = 'change-me-in-local-dev-secret-at-least-32-bytes'
LOCAL_APP_ENVS = {'local', 'test'}
SUPPORTED_JWT_ALGORITHMS = {'HS256'}
MAX_JWT_ACCESS_TOKEN_EXPIRE_MINUTES = 24 * 60
MAX_OTLP_EXPORTER_TIMEOUT_SECONDS = 60
MAX_CACHE_TTL_SECONDS = 24 * 60 * 60


class Settings(BaseSettings):
    app_env: str = Field(default='local', alias='APP_ENV')
    app_name: str = Field(default='Moira', alias='APP_NAME')
    app_debug: bool = Field(default=False, alias='APP_DEBUG')

    database_url: str = Field(
        default='postgresql+asyncpg://moira:moira@localhost:5432/moira',
        alias='DATABASE_URL',
    )

    jwt_secret_key: str = Field(
        default=DEFAULT_LOCAL_JWT_SECRET,
        alias='JWT_SECRET_KEY',
    )
    jwt_algorithm: str = Field(default='HS256', alias='JWT_ALGORITHM')
    jwt_access_token_expire_minutes: int = Field(
        default=30,
        gt=0,
        le=MAX_JWT_ACCESS_TOKEN_EXPIRE_MINUTES,
        alias='JWT_ACCESS_TOKEN_EXPIRE_MINUTES',
    )

    password_hash_scheme: str = Field(default='bcrypt', alias='PASSWORD_HASH_SCHEME')
    default_timezone: str = Field(default='America/Fortaleza', alias='DEFAULT_TIMEZONE')
    log_level: str = Field(default='INFO', alias='LOG_LEVEL')
    log_format: Literal['json', 'console'] = Field(default='json', alias='LOG_FORMAT')
    log_exporters: Annotated[tuple[str, ...], NoDecode] = Field(
        default=('stdout',), alias='LOG_EXPORTERS'
    )
    otel_exporter_otlp_logs_endpoint: AnyHttpUrl | None = Field(
        default=None,
        alias='OTEL_EXPORTER_OTLP_LOGS_ENDPOINT',
    )
    otel_exporter_otlp_headers: SecretStr | None = Field(
        default=None,
        alias='OTEL_EXPORTER_OTLP_HEADERS',
    )
    otel_exporter_otlp_timeout: float = Field(
        default=5,
        gt=0,
        le=MAX_OTLP_EXPORTER_TIMEOUT_SECONDS,
        alias='OTEL_EXPORTER_OTLP_TIMEOUT',
    )
    otel_service_name: str | None = Field(default=None, alias='OTEL_SERVICE_NAME')
    cache_enabled: bool = Field(default=True, alias='CACHE_ENABLED')
    redis_url: SecretStr = Field(
        default=SecretStr('redis://localhost:6379/0'),
        alias='REDIS_URL',
    )
    cache_ttl_public_provider_seconds: int = Field(
        default=1800,
        gt=0,
        le=MAX_CACHE_TTL_SECONDS,
        alias='CACHE_TTL_PUBLIC_PROVIDER_SECONDS',
    )
    cache_ttl_public_offerings_seconds: int = Field(
        default=600,
        gt=0,
        le=MAX_CACHE_TTL_SECONDS,
        alias='CACHE_TTL_PUBLIC_OFFERINGS_SECONDS',
    )
    cache_ttl_available_slots_seconds: int = Field(
        default=30,
        gt=0,
        le=MAX_CACHE_TTL_SECONDS,
        alias='CACHE_TTL_AVAILABLE_SLOTS_SECONDS',
    )
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=list, alias='CORS_ALLOWED_ORIGINS'
    )

    model_config = SettingsConfigDict(
        env_file='.env',
        env_file_encoding='utf_8',
        extra='ignore',
    )

    @field_validator('app_env', mode='before')
    @classmethod
    def normalize_app_env(cls, value: str) -> str:
        return str(value).strip().lower()

    @field_validator('cors_allowed_origins', mode='before')
    @classmethod
    def parse_cors_allowed_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            if not value.strip():
                return []

            return [origin.strip() for origin in value.split(',') if origin.strip()]

        return value

    @field_validator('jwt_algorithm', mode='before')
    @classmethod
    def validate_jwt_algorithm(cls, value: str) -> str:
        normalized = str(value).strip().upper()
        if normalized not in SUPPORTED_JWT_ALGORITHMS:
            raise ValueError(
                f'JWT_ALGORITHM must be one of {sorted(SUPPORTED_JWT_ALGORITHMS)}'
            )
        return normalized

    @field_validator('default_timezone')
    @classmethod
    def validate_default_timezone(cls, value: str) -> str:
        try:
            ZoneInfo(value)
        except ZoneInfoNotFoundError as exc:
            raise ValueError('DEFAULT_TIMEZONE must be a valid IANA timezone') from exc
        return value

    @field_validator('log_level', mode='before')
    @classmethod
    def validate_log_level(cls, value: str) -> str:
        normalized = str(value).upper()
        allowed = {'DEBUG', 'INFO', 'WARNING', 'ERROR', 'CRITICAL'}
        if normalized not in allowed:
            raise ValueError(f'LOG_LEVEL must be one of {sorted(allowed)}')
        return normalized

    @field_validator('log_format', mode='before')
    @classmethod
    def normalize_log_format(cls, value: str) -> str:
        return str(value).lower()

    @field_validator('log_exporters', mode='before')
    @classmethod
    def parse_log_exporters(cls, value: str | tuple[str, ...]) -> tuple[str, ...]:
        if isinstance(value, str):
            exporters = tuple(
                item.strip().lower() for item in value.split(',') if item.strip()
            )
        else:
            exporters = tuple(str(item).lower() for item in value)

        allowed = {'stdout', 'otlp'}
        if not exporters or set(exporters) - allowed:
            raise ValueError('LOG_EXPORTERS accepts only stdout or stdout,otlp')
        if 'stdout' not in exporters:
            raise ValueError('LOG_EXPORTERS must include stdout')
        if len(set(exporters)) != len(exporters):
            raise ValueError('LOG_EXPORTERS must not contain duplicates')
        return exporters

    @model_validator(mode='after')
    def validate_runtime_configuration(self) -> 'Settings':
        if self.app_env not in LOCAL_APP_ENVS:
            secret = self.jwt_secret_key.strip()
            if secret == DEFAULT_LOCAL_JWT_SECRET or len(secret) < 32:
                raise ValueError(
                    'JWT_SECRET_KEY must be changed to a strong secret outside '
                    'local/test'
                )

        if 'otlp' in self.log_exporters and not self.otel_exporter_otlp_logs_endpoint:
            raise ValueError(
                'OTEL_EXPORTER_OTLP_LOGS_ENDPOINT is required when otlp is enabled'
            )
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()
