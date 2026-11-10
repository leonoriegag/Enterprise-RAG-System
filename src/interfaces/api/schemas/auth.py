"""Authentication request and response schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, EmailStr, Field


class TokenRequest(BaseModel):
    """User credentials for token acquisition."""

    email: EmailStr = Field(..., description="Corporate user email address")
    password: str = Field(..., min_length=8, description="User password")
    tenant_slug: str = Field(..., description="Tenant organization slug")


class TokenResponse(BaseModel):
    """JWT bearer token response."""

    access_token: str = Field(..., description="Signed JSON Web Token")
    token_type: str = Field(default="bearer", description="Token authentication scheme")
    expires_in: int = Field(..., description="Token validity duration in seconds")


class UserProfileResponse(BaseModel):
    """Authenticated caller profile and authorization claims."""

    user_id: UUID
    tenant_id: UUID
    email: EmailStr
    role: str
    department: str
    max_clearance: int
