"""Health and readiness check schemas."""

from __future__ import annotations

from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class HealthStatus(StrEnum):
    """Health status indicator."""

    HEALTHY = "healthy"
    DEGRADED = "degraded"
    UNHEALTHY = "unhealthy"


class ComponentStatus(BaseModel):
    """Status detail for a system component."""

    status: HealthStatus
    details: dict[str, Any] | None = None


class HealthResponse(BaseModel):
    """Service health response envelope."""

    status: HealthStatus
    version: str = "0.1.0"
    environment: str
    components: dict[str, ComponentStatus] | None = Field(
        default=None, description="Detailed component readiness statuses"
    )
