"""Tenant administration request and response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class TenantCreateRequest(BaseModel):
    """Parameters for provisioning a new tenant organization."""

    name: str = Field(..., min_length=2, max_length=100, description="Organization display name")
    slug: str = Field(
        ...,
        min_length=2,
        max_length=50,
        pattern=r"^[a-z0-9-]+$",
        description="Unique URL-friendly tenant identifier",
    )


class TenantResponse(BaseModel):
    """Tenant organization representation."""

    id: UUID
    name: str
    slug: str
    is_active: bool
    created_at: datetime


class TenantListResponse(BaseModel):
    """List of active tenants."""

    total: int
    items: list[TenantResponse]
