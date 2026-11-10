"""Tests for /api/v1/documents document lifecycle endpoints."""

from __future__ import annotations

import io
from typing import Any
from uuid import UUID

import pytest
from httpx import AsyncClient


@pytest.mark.asyncio
async def test_list_documents_requires_auth(client: AsyncClient) -> None:
    """GET /api/v1/documents without a bearer token must return 401."""
    response = await client.get("/api/v1/documents")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_list_documents_hr_user_sees_hr_docs(
    client: AsyncClient, app_context: dict[str, Any]
) -> None:
    """HR user should see the HR leave_doc seeded in conftest app_context."""
    hr_token = app_context["hr_token"]
    response = await client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert "items" in data
    assert "total" in data
    # leave_doc is in HR department — HR user has access
    titles = [item["title"] for item in data["items"]]
    assert "Employee Leave Policy" in titles


@pytest.mark.asyncio
async def test_list_documents_it_user_cannot_see_hr_docs(
    client: AsyncClient, app_context: dict[str, Any]
) -> None:
    """IT user must NOT see HR-department documents (department boundary enforcement)."""
    it_token = app_context["it_token"]
    response = await client.get(
        "/api/v1/documents",
        headers={"Authorization": f"Bearer {it_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    # leave_doc is in HR — IT user has no access to it
    titles = [item["title"] for item in data["items"]]
    assert "Employee Leave Policy" not in titles


@pytest.mark.asyncio
async def test_get_document_returns_404_for_other_tenant(
    client: AsyncClient, app_context: dict[str, Any]
) -> None:
    """Fetching a document that belongs to a different tenant must return 404."""
    leave_doc_id = app_context["leave_doc"].id
    other_token = app_context["other_token"]  # belongs to other_tenant

    response = await client.get(
        f"/api/v1/documents/{leave_doc_id}",
        headers={"Authorization": f"Bearer {other_token}"},
    )
    assert response.status_code == 404


@pytest.mark.asyncio
async def test_get_document_returns_403_for_wrong_department(
    client: AsyncClient, app_context: dict[str, Any]
) -> None:
    """IT user requesting an HR document within same tenant must receive 403."""
    leave_doc_id = app_context["leave_doc"].id
    it_token = app_context["it_token"]

    response = await client.get(
        f"/api/v1/documents/{leave_doc_id}",
        headers={"Authorization": f"Bearer {it_token}"},
    )
    # leave_doc is HR; IT user is not in HR department
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_get_document_hr_user_can_access_own_dept_doc(
    client: AsyncClient, app_context: dict[str, Any]
) -> None:
    """HR user should successfully retrieve the leave_doc metadata."""
    leave_doc_id = app_context["leave_doc"].id
    hr_token = app_context["hr_token"]

    response = await client.get(
        f"/api/v1/documents/{leave_doc_id}",
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["title"] == "Employee Leave Policy"
    assert data["department"] == "hr"
    assert isinstance(data["chunk_count"], int)


@pytest.mark.asyncio
async def test_delete_document_requires_auth(
    client: AsyncClient, app_context: dict[str, Any]
) -> None:
    """DELETE /api/v1/documents/{id} without token must return 401."""
    leave_doc_id = app_context["leave_doc"].id
    response = await client.delete(f"/api/v1/documents/{leave_doc_id}")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_delete_document_hr_member_cannot_delete(
    client: AsyncClient, app_context: dict[str, Any]
) -> None:
    """Non-admin HR member should be forbidden from deleting a document (403)."""
    leave_doc_id = app_context["leave_doc"].id
    hr_token = app_context["hr_token"]  # MEMBER role

    response = await client.delete(
        f"/api/v1/documents/{leave_doc_id}",
        headers={"Authorization": f"Bearer {hr_token}"},
    )
    assert response.status_code == 403


@pytest.mark.asyncio
async def test_delete_document_admin_can_delete(
    client: AsyncClient, app_context: dict[str, Any]
) -> None:
    """ADMIN can delete any document within their tenant."""
    leave_doc_id: UUID = app_context["leave_doc"].id
    admin_token = app_context["admin_token"]

    response = await client.delete(
        f"/api/v1/documents/{leave_doc_id}",
        headers={"Authorization": f"Bearer {admin_token}"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["deleted"] is True
    assert str(leave_doc_id) == data["document_id"]


@pytest.mark.asyncio
async def test_upload_document_via_multipart(
    client: AsyncClient, app_context: dict[str, Any]
) -> None:
    """POST /api/v1/documents/upload with valid markdown content should return 201."""
    admin_token = app_context["admin_token"]
    file_content = b"# IT Security Policy\n\nAll laptops must be encrypted.\n"

    response = await client.post(
        "/api/v1/documents/upload",
        headers={"Authorization": f"Bearer {admin_token}"},
        files={"file": ("security_policy.md", io.BytesIO(file_content), "text/markdown")},
        data={"title": "IT Security Policy", "department": "it", "access_level": "20"},
    )
    assert response.status_code == 201
    data = response.json()
    assert data["title"] == "IT Security Policy"
    assert data["chunks_created"] >= 1
    assert data["is_duplicate"] is False
    assert "document_id" in data
