from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

import app.main as app_main
from app.config import Settings
from app.main import create_app


def test_create_app_returns_fastapi_instance() -> None:
    app = create_app()

    assert isinstance(app, FastAPI)


def test_create_app_does_not_install_cors_when_origins_are_empty(
    monkeypatch,
) -> None:
    monkeypatch.setattr(
        app_main,
        'get_settings',
        lambda: Settings.model_validate({'CORS_ALLOWED_ORIGINS': []}),
    )

    app = create_app()

    assert all(
        middleware.cls is not CORSMiddleware for middleware in app.user_middleware
    )


def test_create_app_installs_cors_when_origins_are_configured(monkeypatch) -> None:
    monkeypatch.setattr(
        app_main,
        'get_settings',
        lambda: Settings.model_validate(
            {'CORS_ALLOWED_ORIGINS': 'http://localhost:3000'}
        ),
    )

    app = create_app()

    cors_middleware = next(
        middleware
        for middleware in app.user_middleware
        if middleware.cls is CORSMiddleware
    )
    assert cors_middleware.kwargs['allow_origins'] == ['http://localhost:3000']
    assert cors_middleware.kwargs['allow_credentials'] is True
    assert cors_middleware.kwargs['allow_methods'] == ['GET', 'POST', 'PATCH']
    assert cors_middleware.kwargs['allow_headers'] == [
        'Authorization',
        'Content-Type',
        'Idempotency-Key',
        'X-Correlation-ID',
    ]
