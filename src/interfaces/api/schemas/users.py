"""User administration request and response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class UserCreateRequest(BaseModel):
    """Parameters for creating a tenant user."""

    email: EmailStr = Field(..., description="User corporate email address")
    password: str = Field(..., min_length=8, description="Initial temporary password")
    role: str = Field(default="member", description="User role: 'admin', 'lead', or 'member'")
    department: str = Field(
        default="general",
        description="Assigned department (e.g. 'general', 'hr', 'it', 'engineering')",
    )
    max_clearance: int | None = Field(
        default=None,
        description="Optional explicit maximum classification clearance (10, 20, 30, 40)",
    )


class UserResponse(BaseModel):
    """User account details."""

    id: UUID
    tenant_id: UUID
    email: EmailStr
    role: str
    department: str
    max_clearance: int
    is_active: bool
    created_at: datetime


class UserListResponse(BaseModel):
    """List of users in tenant."""

    total: int
    items: list[UserResponse]
