"""FastAPI middleware for correlation ID propagation and request access logging."""

import time
import uuid
from collections.abc import Callable
from typing import Any

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware

from src.shared.logging import correlation_id_ctx, get_logger

logger = get_logger("api.access")


class CorrelationIdMiddleware(BaseHTTPMiddleware):
    """Middleware attaching unique correlation ID to requests and response headers."""

    async def dispatch(self, request: Request, call_next: Callable[..., Any]) -> Response:
        # Extract existing or generate new correlation / trace ID
        incoming_id = request.headers.get("X-Correlation-ID")
        correlation_id = incoming_id if incoming_id else str(uuid.uuid4())

        # Bind to contextual variable for all downstream loggers
        token = correlation_id_ctx.set(correlation_id)

        start_time = time.monotonic()
        client_ip = request.client.host if request.client else "unknown"

        try:
            response: Response = await call_next(request)
            duration_ms = (time.monotonic() - start_time) * 1000

            # Set tracking header on response
            response.headers["X-Correlation-ID"] = correlation_id

            # Log sanitized access event
            logger.info(
                f"{request.method} {request.url.path} "
                f"status={response.status_code} "
                f"duration={duration_ms:.2f}ms client={client_ip}"
            )
            return response
        except Exception as exc:
            duration_ms = (time.monotonic() - start_time) * 1000
            logger.error(
                f"Unhandled exception during {request.method} {request.url.path} "
                f"duration={duration_ms:.2f}ms error={exc}"
            )
            raise
        finally:
            correlation_id_ctx.reset(token)
