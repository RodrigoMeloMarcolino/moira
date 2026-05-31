from app.config import Settings


def test_sessings_defaults() -> None:
    settings = Settings()

    assert settings.app_name == "moira"
    assert settings.app_debug
    assert settings.database_url.startswith("postgresql+asyncpg://")
    assert settings.default_timezone == "America/Fortaleza"