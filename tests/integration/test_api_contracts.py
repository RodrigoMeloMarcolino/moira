import pytest
from httpx import ASGITransport, AsyncClient

from tests.integration.conftest import unique_value

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_legacy_unversioned_routes_are_not_registered(
    client: AsyncClient,
) -> None:
    response = await client.get('/health')

    assert response.status_code == 404
    assert response.json() == {
        'error': {
            'code': 'not_found',
            'message': 'Not Found',
            'details': None,
        }
    }
    assert response.headers['X-Request-ID']
    assert response.headers['X-Correlation-ID']


async def test_not_found_errors_use_error_envelope(client: AsyncClient) -> None:
    response = await client.get(f'/v1/public/providers/{unique_value("missing")}')

    assert response.status_code == 404
    assert response.json() == {
        'error': {
            'code': 'provider_not_found',
            'message': 'provider not found',
            'details': None,
        }
    }


async def test_validation_errors_use_error_envelope(client: AsyncClient) -> None:
    response = await client.post(
        '/v1/providers/signup',
        json={
            'email': 'provider@example.com',
            'password': 'short',
            'display_name': 'Provider Test',
        },
    )

    assert response.status_code == 422
    body = response.json()
    assert body['error']['code'] == 'validation_error'
    assert body['error']['message'] == 'request validation failed'
    assert body['error']['details']


async def test_valid_correlation_id_is_preserved(client: AsyncClient) -> None:
    response = await client.get(
        '/v1/health', headers={'X-Correlation-ID': 'integration-operation-123'}
    )

    assert response.status_code == 200
    assert response.headers['X-Correlation-ID'] == 'integration-operation-123'
    assert response.headers['X-Request-ID'] != 'integration-operation-123'


async def test_unexpected_errors_use_safe_correlated_envelope(caplog) -> None:
    from app.main import create_app

    app = create_app()

    @app.get('/v1/test-unexpected-error')
    async def unexpected_error() -> None:
        raise RuntimeError('database detail that must stay private')

    async with app.router.lifespan_context(app):
        transport = ASGITransport(app=app, raise_app_exceptions=False)
        async with AsyncClient(
            transport=transport, base_url='http://testserver'
        ) as test_client:
            response = await test_client.get('/v1/test-unexpected-error')

    assert response.status_code == 500
    assert response.headers['X-Request-ID']
    assert response.headers['X-Correlation-ID'] == response.headers['X-Request-ID']
    assert response.json() == {
        'error': {
            'code': 'internal_server_error',
            'message': 'internal server error',
            'details': None,
        }
    }
    failures = [
        record
        for record in caplog.records
        if getattr(record, 'event_name', None) == 'http.request.failed'
    ]
    assert len(failures) == 1
    assert 'database detail' not in failures[0].getMessage()
