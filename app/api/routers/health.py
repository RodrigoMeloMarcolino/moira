from fastapi import APIRouter, status
from fastapi.responses import JSONResponse

from app.database import check_database_ready

health_router  = APIRouter(tags=["health"])

@health_router.get("/health")
async def health() -> JSONResponse:
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "ok"}
    )

@health_router.get("/ready")
async def ready() -> JSONResponse:
    database_ready = await check_database_ready()

    if not database_ready:
        return JSONResponse(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            content={"status": "not_ready"}
        )
    
    return JSONResponse(
        status_code=status.HTTP_200_OK,
        content={"status": "ready"}
    )