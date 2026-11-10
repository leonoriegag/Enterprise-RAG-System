"""Tests for /api/v1/auth authentication and token lifecycle endpoints."""

from typing import Any

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_login_success_returns_jwt_token(
    client: AsyncClient, app_context: dict[str, Any]
) -> None:
    """POST /api/v1/auth/token with valid credentials must issue signed JWT."""
    response = await client.post(
        "/api/v1/auth/token",
        json={
            "email": "hr@acme.corp",
            "password": "Password123!",
            "tenant_slug": "acme",
        },
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["expires_in"] > 0


@pytest.mark.asyncio
async def test_login_invalid_password_returns_401(client: AsyncClient) -> None:
    """POST /api/v1/auth/token with invalid password must return 401."""
    response = await client.post(
        "/api/v1/auth/token",
        json={
            "email": "hr@acme.corp",
            "password": "WrongPassword!",
            "tenant_slug": "acme",
        },
    )
    assert response.status_code == 401
    assert "Invalid organization or credentials" in response.text


@pytest.mark.asyncio
async def test_login_nonexistent_tenant_returns_401(client: AsyncClient) -> None:
    """POST /api/v1/auth/token with invalid tenant slug must return 401."""
    response = await client.post(
        "/api/v1/auth/token",
        json={
            "email": "hr@acme.corp",
            "password": "Password123!",
            "tenant_slug": "nonexistent-tenant",
        },
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_current_user_profile(client: AsyncClient, app_context: dict[str, Any]) -> None:
    """GET /api/v1/auth/me with valid Bearer token returns decoded user claims."""
    token = app_context["hr_token"]
    response = await client.get(
        "/api/v1/auth/me",
        headers={"Authorization": f"Bearer {token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["email"] == "hr@acme.corp"
    assert data["role"] == "member"
    assert data["department"] == "hr"
    assert data["max_clearance"] == 20
    assert data["tenant_id"] == str(app_context["acme_tenant"].id)


@pytest.mark.asyncio
async def test_get_profile_without_token_returns_401(client: AsyncClient) -> None:
    """GET /api/v1/auth/me without token must return 401."""
    response = await client.get("/api/v1/auth/me")
    assert response.status_code == 401
