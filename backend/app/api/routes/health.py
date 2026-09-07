from fastapi import APIRouter, HTTPException, status

from app.db.session import DatabaseUnavailableError, check_database_connection
from app.schemas.health import DatabaseHealthResponse, HealthResponse

router = APIRouter(tags=["system"])


@router.get("/health", response_model=HealthResponse)
async def health_check() -> HealthResponse:
    return HealthResponse(status="ok", service="essay-evaluation-api")


@router.get("/health/database", response_model=DatabaseHealthResponse)
async def database_health_check() -> DatabaseHealthResponse:
    try:
        await check_database_connection()
    except DatabaseUnavailableError as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Database unavailable",
        ) from exc

    return DatabaseHealthResponse(status="ok", database="postgresql")
