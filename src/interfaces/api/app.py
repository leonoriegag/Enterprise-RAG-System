"""FastAPI application factory, lifespan management, and global exception handlers."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Request, status
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from src.domain.exceptions import (
    AccessDeniedError,
    CrossTenantViolationError,
    DocumentNotFoundError,
    IngestionError,
)
from src.infrastructure.database.session import get_engine
from src.interfaces.api.middleware import CorrelationIdMiddleware
from src.interfaces.api.routers import (
    admin_router,
    auth_router,
    documents_router,
    health_router,
    rag_router,
    retrieval_router,
)
from src.interfaces.api.schemas.common import ErrorDetail, ErrorResponse
from src.shared.config import Settings, get_settings
from src.shared.logging import configure_logging, correlation_id_ctx, get_logger

logger = get_logger("api.app")


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncGenerator[None, None]:
    """Application lifespan managing logger setup and connection pools."""
    settings = get_settings()
    configure_logging(level=settings.LOG_LEVEL, json_format=True)
    logger.info(
        f"Starting {settings.APP_NAME} in '{settings.APP_ENV}' mode "
        f"(embedding={settings.EMBEDDING_PROVIDER}, llm={settings.LLM_PROVIDER})"
    )

    yield

    # Clean shutdown of database engine
    engine = get_engine(settings)
    await engine.dispose()
    logger.info("Application shutdown complete. Database engine disposed.")


def create_app(_settings: Settings | None = None) -> FastAPI:
    """FastAPI application factory configured for enterprise RAG operations."""
    app = FastAPI(
        title="Enterprise RAG System API",
        version="0.1.0",
        description=(
            "Enterprise knowledge assistant REST API featuring hybrid retrieval, "
            "PostgreSQL Row-Level Security (RLS) multi-tenancy, grounded generation, "
            "document-level access clearance enforcement, and verifiable source citations."
        ),
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        lifespan=lifespan,
    )

    # 1. Middlewares (outermost first)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    app.add_middleware(CorrelationIdMiddleware)

    # 2. Domain & Application Exception Handlers
    @app.exception_handler(AccessDeniedError)
    async def access_denied_handler(_request: Request, exc: AccessDeniedError) -> JSONResponse:
        correlation_id = correlation_id_ctx.get()
        logger.warning(f"Access denied: {exc} [correlation_id={correlation_id}]")
        payload = ErrorResponse(
            error=ErrorDetail(code="ACCESS_DENIED", message=str(exc)),
            correlation_id=correlation_id,
        )
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content=payload.model_dump())

    @app.exception_handler(CrossTenantViolationError)
    async def cross_tenant_handler(
        _request: Request, exc: CrossTenantViolationError
    ) -> JSONResponse:
        correlation_id = correlation_id_ctx.get()
        logger.error(
            f"Security Alert: Cross-tenant violation: {exc} [correlation_id={correlation_id}]"
        )
        payload = ErrorResponse(
            error=ErrorDetail(code="CROSS_TENANT_VIOLATION", message=str(exc)),
            correlation_id=correlation_id,
        )
        return JSONResponse(status_code=status.HTTP_403_FORBIDDEN, content=payload.model_dump())

    @app.exception_handler(DocumentNotFoundError)
    async def not_found_handler(_request: Request, exc: DocumentNotFoundError) -> JSONResponse:
        correlation_id = correlation_id_ctx.get()
        payload = ErrorResponse(
            error=ErrorDetail(code="NOT_FOUND", message=str(exc)),
            correlation_id=correlation_id,
        )
        return JSONResponse(status_code=status.HTTP_404_NOT_FOUND, content=payload.model_dump())

    @app.exception_handler(IngestionError)
    async def ingestion_error_handler(_request: Request, exc: IngestionError) -> JSONResponse:
        correlation_id = correlation_id_ctx.get()
        logger.warning(f"Ingestion processing error: {exc} [correlation_id={correlation_id}]")
        payload = ErrorResponse(
            error=ErrorDetail(code="INGESTION_ERROR", message=str(exc)),
            correlation_id=correlation_id,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=payload.model_dump()
        )

    @app.exception_handler(RequestValidationError)
    async def validation_error_handler(
        _request: Request, exc: RequestValidationError
    ) -> JSONResponse:
        correlation_id = correlation_id_ctx.get()
        payload = ErrorResponse(
            error=ErrorDetail(
                code="VALIDATION_ERROR",
                message="Request validation failed",
                details={"errors": exc.errors()},
            ),
            correlation_id=correlation_id,
        )
        return JSONResponse(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, content=payload.model_dump()
        )

    @app.exception_handler(HTTPException)
    async def http_exception_handler(_request: Request, exc: HTTPException) -> JSONResponse:
        correlation_id = correlation_id_ctx.get()
        payload = ErrorResponse(
            error=ErrorDetail(
                code=f"HTTP_{exc.status_code}",
                message=str(exc.detail),
            ),
            correlation_id=correlation_id,
        )
        return JSONResponse(
            status_code=exc.status_code,
            headers=exc.headers,
            content=payload.model_dump(),
        )

    @app.exception_handler(Exception)
    async def generic_exception_handler(_request: Request, exc: Exception) -> JSONResponse:
        correlation_id = correlation_id_ctx.get()
        logger.exception(f"Unhandled server error: {exc} [correlation_id={correlation_id}]")
        payload = ErrorResponse(
            error=ErrorDetail(
                code="INTERNAL_SERVER_ERROR",
                message="An internal server error occurred. Please contact system administration.",
            ),
            correlation_id=correlation_id,
        )
        return JSONResponse(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            content=payload.model_dump(),
        )

    # 3. Mount Routers
    app.include_router(health_router)
    app.include_router(auth_router)
    app.include_router(documents_router)
    app.include_router(retrieval_router)
    app.include_router(rag_router)
    app.include_router(admin_router)

    return app
