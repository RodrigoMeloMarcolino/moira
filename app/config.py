from functools import lru_cache
from typing import Annotated

from pydantic import Field, field_validator
from pydantic_settings import BaseSettings, NoDecode, SettingsConfigDict


class Settings(BaseSettings):
    app_env: str = Field(default="local", alias="APP_ENV")
    app_name: str = Field(default="Moira", alias="APP_NAME")
    app_debug: bool = Field(default=False, alias="APP_DEBUG")

    database_url: str = Field(
        default="postgresql+asyncpg://moira:moira@localhost:5432/moira",
        alias="DATABASE_URL",
    )

    jwt_secret_key: str = Field(
        default="change-me-in-local-dev",
        alias="JWT_SECRET_KEY"
    )
    jwt_algorithm: str = Field(default="HS256", alias="JWT_ALGORITHM")
    jwt_access_token_expire_minutes: int = Field(
        default=30,
        alias="JWT_ACCESS_TOKEN_EXPIRE_MINUTES",
    )

    password_hash_scheme: str = Field(default="bcrypt", alias="PASSWORD_HASH_SCHEME")
    default_timezone: str = Field(default="America/Fortaleza", alias="DEFAULT_TIMEZONE")
    log_level: str = Field(default="INFO", alias="LOG_LEVEL")
    cors_allowed_origins: Annotated[list[str], NoDecode] = Field(
        default_factory=list,
        alias="CORS_ALLOWED_ORIGINS"
        )

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf_8",
        extra="ignore",
    )

    @field_validator("cors_allowed_origins", mode="before")
    @classmethod
    def parse_cors_allowed_origins(cls, value: str | list[str]) -> list[str]:
        if isinstance(value, str):
            if not value.strip():
                return []
            
            return [origin.strip() for origin in value.split(",") if origin.strip()]
        
        return value
    
@lru_cache
def get_settings() -> Settings:
    return Settings()