"""Unit tests for multi-tenant and document authorization policies."""

from uuid import uuid4

import pytest

from src.application.auth.context import AuthContext
from src.application.auth.policies import AuthorizationPolicy
from src.domain.entities.document import Document
from src.domain.exceptions import AccessDeniedError, CrossTenantViolationError
from src.domain.value_objects.access_level import AccessLevel
from src.domain.value_objects.department import Department
from src.domain.value_objects.role import UserRole


@pytest.fixture
def tenant_a_id():
    return uuid4()


@pytest.fixture
def tenant_b_id():
    return uuid4()


@pytest.fixture
def hr_member_tenant_a(tenant_a_id):
    return AuthContext(
        tenant_id=tenant_a_id,
        user_id=uuid4(),
        email="hr.member@tenant-a.com",
        role=UserRole.MEMBER,
        department=Department.HR,
        max_clearance=AccessLevel.INTERNAL,
    )


@pytest.fixture
def eng_member_tenant_a(tenant_a_id):
    return AuthContext(
        tenant_id=tenant_a_id,
        user_id=uuid4(),
        email="eng.member@tenant-a.com",
        role=UserRole.MEMBER,
        department=Department.ENGINEERING,
        max_clearance=AccessLevel.INTERNAL,
    )


@pytest.fixture
def admin_tenant_a(tenant_a_id):
    return AuthContext(
        tenant_id=tenant_a_id,
        user_id=uuid4(),
        email="admin@tenant-a.com",
        role=UserRole.ADMIN,
        department=Department.SECURITY,
        max_clearance=AccessLevel.RESTRICTED,
    )


def test_cross_tenant_isolation_raises_error(hr_member_tenant_a, tenant_b_id):
    """Attempting cross-tenant access must strictly raise CrossTenantViolationError."""
    with pytest.raises(CrossTenantViolationError):
        AuthorizationPolicy.validate_tenant_access(hr_member_tenant_a, tenant_b_id)


def test_document_cross_tenant_read_rejected(hr_member_tenant_a, tenant_b_id):
    """User cannot read document belonging to another tenant."""
    doc_tenant_b = Document(
        tenant_id=tenant_b_id,
        title="Secret Tenant B",
        file_path="/files/b.pdf",
        mime_type="application/pdf",
        file_size_bytes=100,
        content_hash="hashb",
        department=Department.HR,
        access_level=AccessLevel.PUBLIC,
    )
    assert AuthorizationPolicy.can_read_document(hr_member_tenant_a, doc_tenant_b) is False
    with pytest.raises(AccessDeniedError):
        AuthorizationPolicy.enforce_read_document(hr_member_tenant_a, doc_tenant_b)


def test_department_boundary_enforcement(hr_member_tenant_a, eng_member_tenant_a, tenant_a_id):
    """Engineering member cannot read HR departmental documents, but HR member can."""
    hr_doc = Document(
        tenant_id=tenant_a_id,
        title="HR Internal Guidelines",
        file_path="/files/hr.pdf",
        mime_type="application/pdf",
        file_size_bytes=100,
        content_hash="hashhr",
        department=Department.HR,
        access_level=AccessLevel.INTERNAL,
    )
    assert AuthorizationPolicy.can_read_document(hr_member_tenant_a, hr_doc) is True
    assert AuthorizationPolicy.can_read_document(eng_member_tenant_a, hr_doc) is False


def test_general_department_accessible_to_all_in_tenant(eng_member_tenant_a, tenant_a_id):
    """Company-wide general documents are accessible to any department member."""
    general_doc = Document(
        tenant_id=tenant_a_id,
        title="Company Holidays 2026",
        file_path="/files/holidays.pdf",
        mime_type="application/pdf",
        file_size_bytes=100,
        content_hash="hashholidays",
        department=Department.GENERAL,
        access_level=AccessLevel.INTERNAL,
    )
    assert AuthorizationPolicy.can_read_document(eng_member_tenant_a, general_doc) is True


def test_classification_level_clearance_enforcement(hr_member_tenant_a, tenant_a_id):
    """Member with INTERNAL clearance cannot view CONFIDENTIAL or RESTRICTED documents."""
    restricted_hr_doc = Document(
        tenant_id=tenant_a_id,
        title="Executive Severance Packages",
        file_path="/files/exec.pdf",
        mime_type="application/pdf",
        file_size_bytes=100,
        content_hash="hashexec",
        department=Department.HR,
        access_level=AccessLevel.RESTRICTED,
    )
    assert AuthorizationPolicy.can_read_document(hr_member_tenant_a, restricted_hr_doc) is False


def test_admin_has_full_tenant_clearance(admin_tenant_a, tenant_a_id):
    """Admin has clearance across all departments and all classification tiers in tenant."""
    restricted_hr_doc = Document(
        tenant_id=tenant_a_id,
        title="Executive Severance Packages",
        file_path="/files/exec.pdf",
        mime_type="application/pdf",
        file_size_bytes=100,
        content_hash="hashexec",
        department=Department.HR,
        access_level=AccessLevel.RESTRICTED,
    )
    assert AuthorizationPolicy.can_read_document(admin_tenant_a, restricted_hr_doc) is True


def test_upload_and_delete_permissions(hr_member_tenant_a, admin_tenant_a, tenant_a_id):
    """Members cannot upload to other departments; only admins/managers can delete."""
    assert AuthorizationPolicy.can_upload_to_department(hr_member_tenant_a, Department.HR) is True
    assert (
        AuthorizationPolicy.can_upload_to_department(hr_member_tenant_a, Department.ENGINEERING)
        is False
    )

    doc = Document(
        tenant_id=tenant_a_id,
        title="HR Policy",
        file_path="/files/hr.pdf",
        mime_type="application/pdf",
        file_size_bytes=100,
        content_hash="hashhr",
        department=Department.HR,
        access_level=AccessLevel.INTERNAL,
    )
    assert AuthorizationPolicy.can_delete_document(hr_member_tenant_a, doc) is False
    assert AuthorizationPolicy.can_delete_document(admin_tenant_a, doc) is True
