"""Tests for /api/v1/admin tenant and user administration endpoints."""

from __future__ import annotations

from typing import Any

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_admin_routes_require_auth(client: AsyncClient) -> None:
    """Admin endpoints without bearer token must return 401."""
    for path in ["/api/v1/admin/tenants", "/api/v1/admin/users"]:
        response = await client.get(path)
        assert response.status_code == 401, f"Expected 401 for {path}, got {response.status_code}"


@pytest.mark.asyncio
async def test_non_admin_cannot_access_admin_routes(
    client: AsyncClient, app_context: dict[str, Any]
) -> None:
    """Non-admin (MEMBER) user must receive 403 on all admin endpoints."""
    hr_token = app_context["hr_token"]  # MEMBER role
    for path in ["/api/v1/admin/tenants", "/api/v1/admin/users"]:
        response = await client.get(path, headers={"Authorization": f"Bearer {hr_token}"})
        assert response.status_code == 403, f"Expected 403 for {path}, got {response.status_code}"


@pytest.mark.asyncio
async def test_admin_can_list_tenants(client: AsyncClient, app_context: dict[str, Any]) -> None:
    """ADMIN user can list active tenants and receives correct shape."""
    admin_token = app_context["admin_token"]
    response = await client.get(
        "/api/v1/admin/tenants",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)
    # Both acme and other tenants were seeded
    assert data["total"] >= 1
    slugs = [t["slug"] for t in data["items"]]
    assert "acme" in slugs


@pytest.mark.asyncio
async def test_admin_can_create_tenant(client: AsyncClient, app_context: dict[str, Any]) -> None:
    """ADMIN user can provision a new tenant."""
    admin_token = app_context["admin_token"]
    response = await client.post(
        "/api/v1/admin/tenants",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "New Corp", "slug": "newcorp"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["slug"] == "newcorp"
    assert data["name"] == "New Corp"
    assert data["is_active"] is True


@pytest.mark.asyncio
async def test_create_tenant_conflict_on_duplicate_slug(
    client: AsyncClient, app_context: dict[str, Any]
) -> None:
    """Creating a tenant with an already-used slug must return 409 Conflict."""
    admin_token = app_context["admin_token"]
    response = await client.post(
        "/api/v1/admin/tenants",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={"name": "ACME Duplicate", "slug": "acme"},
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_admin_can_list_users(client: AsyncClient, app_context: dict[str, Any]) -> None:
    """ADMIN can retrieve all users belonging to their tenant."""
    admin_token = app_context["admin_token"]
    response = await client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "total" in data
    assert "items" in data
    assert isinstance(data["items"], list)
    emails = [u["email"] for u in data["items"]]
    # admin, hr, it users belong to acme tenant
    assert "admin@acme.corp" in emails
    assert "hr@acme.corp" in emails
    assert "it@acme.corp" in emails
    # other tenant's user must NOT appear
    assert "user@other.corp" not in emails


@pytest.mark.asyncio
async def test_admin_can_create_user(client: AsyncClient, app_context: dict[str, Any]) -> None:
    """ADMIN can provision a new user within their tenant."""
    admin_token = app_context["admin_token"]
    response = await client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": "finance@acme.corp",
            "password": "SecurePass999!",
            "role": "member",
            "department": "finance",
        },
    )
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "finance@acme.corp"
    assert data["department"] == "finance"
    assert data["role"] == "member"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_user_conflict_on_duplicate_email(
    client: AsyncClient, app_context: dict[str, Any]
) -> None:
    """Creating a user with an email that already exists in the tenant must return 409."""
    admin_token = app_context["admin_token"]
    response = await client.post(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
        json={
            "email": "hr@acme.corp",
            "password": "AnotherPass123!",
            "role": "member",
            "department": "hr",
        },
    )
    assert response.status_code == 409


@pytest.mark.asyncio
async def test_admin_user_response_contains_expected_fields(
    client: AsyncClient, app_context: dict[str, Any]
) -> None:
    """UserResponse schema must expose id, email, role, department, max_clearance, is_active."""
    admin_token = app_context["admin_token"]
    response = await client.get(
        "/api/v1/admin/users",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    items = response.json()["items"]
    assert len(items) > 0
    user = items[0]
    for field in ("id", "tenant_id", "email", "role", "department", "max_clearance", "is_active"):
        assert field in user, f"Missing field '{field}' in UserResponse"
