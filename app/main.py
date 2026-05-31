from fastapi import FastAPI

from app.api.exception_handlers import register_exception_handlers
from app.api.routers.health import health_router
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(
        title=settings.app_name,
        debug=settings.app_debug
    )

    register_exception_handlers(app)
    app.include_router(health_router)

    return app

app = create_app()