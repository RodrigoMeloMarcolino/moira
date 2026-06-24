import logging

import pytest
from fastapi import FastAPI
from httpx import ASGITransport, AsyncClient

from app.api.middleware.request_logging import RequestLoggingMiddleware
from app.shared.infrastructure.observability.logging.context import (
    current_request_context,
)


def _test_app() -> FastAPI:
    app = FastAPI()
    app.add_middleware(RequestLoggingMiddleware)

    @app.get('/items/{item_id}')
    async def item(item_id: str) -> dict[str, str]:
        return {'item_id': item_id}

    @app.get('/boom')
    async def boom() -> None:
        raise RuntimeError('internal detail')

    return app


@pytest.mark.asyncio
async def test_request_headers_and_route_template(caplog) -> None:
    app = _test_app()
    caplog.set_level(logging.INFO)
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.get(
            '/items/secret-path-value?token=hidden',
            headers={'X-Correlation-ID': 'operation-123'},
        )

    assert response.status_code == 200
    assert response.headers['X-Correlation-ID'] == 'operation-123'
    assert response.headers['X-Request-ID'] != 'operation-123'
    records = [
        record
        for record in caplog.records
        if getattr(record, 'event_name', None) == 'http.request.completed'
    ]
    assert len(records) == 1
    assert records[0].__dict__['http.route'] == '/items/{item_id}'
    assert 'secret-path-value' not in records[0].getMessage()
    assert 'hidden' not in records[0].getMessage()
    assert current_request_context() == {}


@pytest.mark.asyncio
async def test_invalid_correlation_is_replaced_and_404_has_headers() -> None:
    transport = ASGITransport(app=_test_app())
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.get(
            '/missing', headers={'X-Correlation-ID': 'contains spaces'}
        )

    assert response.status_code == 404
    assert response.headers['X-Correlation-ID'] == response.headers['X-Request-ID']


@pytest.mark.asyncio
async def test_unexpected_error_returns_safe_correlated_500(caplog) -> None:
    caplog.set_level(logging.ERROR)
    transport = ASGITransport(app=_test_app(), raise_app_exceptions=False)
    async with AsyncClient(transport=transport, base_url='http://test') as client:
        response = await client.get('/boom')

    assert response.status_code == 500
    assert response.json() == {
        'error': {
            'code': 'internal_server_error',
            'message': 'internal server error',
            'details': None,
        }
    }
    assert response.headers['X-Correlation-ID'] == response.headers['X-Request-ID']
    failures = [
        record
        for record in caplog.records
        if getattr(record, 'event_name', None) == 'http.request.failed'
    ]
    assert len(failures) == 1
    assert failures[0].__dict__['exception.type'] == 'RuntimeError'
    assert 'internal detail' not in failures[0].getMessage()
