"""Common API schemas including error responses and pagination."""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field


class ErrorDetail(BaseModel):
    """Structured error information."""

    code: str = Field(..., description="Machine-readable error classification code")
    message: str = Field(..., description="Human-readable error explanation")
    details: dict[str, Any] | None = Field(default=None, description="Optional extra error context")


class ErrorResponse(BaseModel):
    """Standardized top-level error response envelope."""

    error: ErrorDetail
    correlation_id: str = Field(
        ..., description="Distributed tracing identifier for troubleshooting"
    )


class PaginationParams(BaseModel):
    """Standard pagination query parameters."""

    limit: int = Field(default=20, ge=1, le=100, description="Maximum items to return")
    offset: int = Field(default=0, ge=0, description="Offset position for pagination")
