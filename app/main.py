from fastapi import FastAPI

from app.api.exception_handlers import register_exception_handlers
from app.api.routers.appointments import appointments_router
from app.api.routers.auth import auth_router
from app.api.routers.availability import availability_router
from app.api.routers.health import health_router
from app.api.routers.offerings import offerings_router
from app.api.routers.providers import providers_router
from app.config import get_settings


def create_app() -> FastAPI:
    settings = get_settings()

    app = FastAPI(title=settings.app_name, debug=settings.app_debug)

    register_exception_handlers(app)
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(providers_router)
    app.include_router(offerings_router)
    app.include_router(appointments_router)
    app.include_router(availability_router)

    return app


app = create_app()
