import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.exception_handlers import register_exception_handlers
from app.api.middleware.request_logging import RequestLoggingMiddleware
from app.api.routers.appointments import appointments_router
from app.api.routers.auth import auth_router
from app.api.routers.availability import availability_router
from app.api.routers.health import health_router
from app.api.routers.offerings import offerings_router
from app.api.routers.providers import providers_router
from app.config import get_settings
from app.shared.infrastructure.cache import NullCache, build_cache_backend
from app.shared.infrastructure.observability.logging import configure_logging

logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    redis_client = None
    started = False

    try:
        cache_backend, redis_client = await build_cache_backend(settings)
        app.state.cache_backend = cache_backend
        app.state.redis_client = redis_client
        logger.info(
            'Application started',
            extra={
                'event_name': 'application.started',
                'log_format': settings.log_format,
                'log_exporters': list(settings.log_exporters),
                'cache_backend': 'redis' if redis_client is not None else 'null',
            },
        )
        started = True
        yield
    finally:
        if redis_client is not None:
            await redis_client.aclose()
        if started:
            logger.info(
                'Application stopped',
                extra={'event_name': 'application.stopped'},
            )
        app.state.logging_runtime.shutdown()


def create_app() -> FastAPI:
    settings = get_settings()
    logging_runtime = configure_logging(settings)

    app = FastAPI(
        title=settings.app_name,
        debug=settings.app_debug,
        lifespan=lifespan,
    )
    app.state.cache_backend = NullCache()
    app.state.redis_client = None
    app.state.logging_runtime = logging_runtime

    if settings.cors_allowed_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_allowed_origins,
            allow_credentials=True,
            allow_methods=['GET', 'POST', 'PATCH'],
            allow_headers=[
                'Authorization',
                'Content-Type',
                'Idempotency-Key',
                'X-Correlation-ID',
            ],
        )

    register_exception_handlers(app)
    app.add_middleware(RequestLoggingMiddleware)
    app.include_router(health_router, prefix='/v1')
    app.include_router(auth_router, prefix='/v1')
    app.include_router(providers_router, prefix='/v1')
    app.include_router(offerings_router, prefix='/v1')
    app.include_router(appointments_router, prefix='/v1')
    app.include_router(availability_router, prefix='/v1')

    return app


app = create_app()
