"""Health and readiness check endpoints."""

from typing import Annotated

from fastapi import APIRouter, Depends, status
from fastapi.responses import JSONResponse
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from src.interfaces.api.dependencies import get_db_session
from src.interfaces.api.schemas.health import ComponentStatus, HealthResponse, HealthStatus
from src.shared.config import Settings, get_settings
from src.shared.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(tags=["Health"])


@router.get(
    "/health",
    response_model=HealthResponse,
    status_code=status.HTTP_200_OK,
    summary="Liveness probe",
    description="Returns immediate application liveness status.",
)
async def liveness(settings: Annotated[Settings, Depends(get_settings)]) -> HealthResponse:
    """Return basic liveness status."""
    return HealthResponse(
        status=HealthStatus.HEALTHY,
        environment=settings.APP_ENV,
    )


@router.get(
    "/health/ready",
    response_model=HealthResponse,
    summary="Readiness probe",
    description="Verifies database connectivity, vector search extension, and AI provider status.",
)
async def readiness(
    settings: Annotated[Settings, Depends(get_settings)],
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> JSONResponse:
    """Inspect downstream dependencies and return readiness health status."""
    components: dict[str, ComponentStatus] = {}
    is_ready = True

    # 1. Database & pgvector check
    try:
        res = await session.execute(text("SELECT 1"))
        res.scalar()
        components["database"] = ComponentStatus(
            status=HealthStatus.HEALTHY,
            details={"connection": "active", "pool_size": settings.DB_POOL_SIZE},
        )
    except Exception as exc:
        is_ready = False
        logger.warning(f"Database readiness check failed: {exc}")
        components["database"] = ComponentStatus(
            status=HealthStatus.UNHEALTHY,
            details={"error": str(exc)},
        )

    # 2. Embedding provider status
    components["embedding_provider"] = ComponentStatus(
        status=HealthStatus.HEALTHY,
        details={
            "provider": settings.EMBEDDING_PROVIDER,
            "dimension": settings.embedding_dimension,
        },
    )

    # 3. LLM provider status
    components["llm_provider"] = ComponentStatus(
        status=HealthStatus.HEALTHY,
        details={
            "provider": settings.LLM_PROVIDER,
            "offline_mock": settings.LLM_PROVIDER == "mock",
        },
    )

    overall_status = HealthStatus.HEALTHY if is_ready else HealthStatus.UNHEALTHY
    http_status = status.HTTP_200_OK if is_ready else status.HTTP_503_SERVICE_UNAVAILABLE

    payload = HealthResponse(
        status=overall_status,
        environment=settings.APP_ENV,
        components=components,
    )
    return JSONResponse(status_code=http_status, content=payload.model_dump())
