from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.exception_handlers import register_exception_handlers
from app.api.routers.appointments import appointments_router
from app.api.routers.auth import auth_router
from app.api.routers.availability import availability_router
from app.api.routers.health import health_router
from app.api.routers.offerings import offerings_router
from app.api.routers.providers import providers_router
from app.config import get_settings
from app.shared.infrastructure.cache import NullCache, build_cache_backend


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    settings = get_settings()
    cache_backend, redis_client = await build_cache_backend(settings)
    app.state.cache_backend = cache_backend
    app.state.redis_client = redis_client

    try:
        yield
    finally:
        if redis_client is not None:
            await redis_client.aclose()


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.app_debug,
        lifespan=lifespan,
    )
    app.state.cache_backend = NullCache()
    app.state.redis_client = None

    register_exception_handlers(app)
    app.include_router(health_router, prefix='/v1')
    app.include_router(auth_router, prefix='/v1')
    app.include_router(providers_router, prefix='/v1')
    app.include_router(offerings_router, prefix='/v1')
    app.include_router(appointments_router, prefix='/v1')
    app.include_router(availability_router, prefix='/v1')

    return app


app = create_app()
