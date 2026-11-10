"""Fine-grained authorization policies enforcing RBAC and ABAC rules."""

from uuid import UUID

from src.application.auth.context import AuthContext
from src.domain.entities.chunk import DocumentChunk
from src.domain.entities.document import Document
from src.domain.exceptions import AccessDeniedError, CrossTenantViolationError
from src.domain.value_objects.department import Department
from src.domain.value_objects.role import UserRole


class AuthorizationPolicy:
    """Enforces multi-tenant and document-level access control rules."""

    @staticmethod
    def validate_tenant_access(auth_context: AuthContext, target_tenant_id: UUID) -> None:
        """Verify that caller belongs strictly to target tenant."""
        if auth_context.tenant_id != target_tenant_id:
            raise CrossTenantViolationError(
                f"Cross-tenant access violation: Caller tenant {auth_context.tenant_id} "
                f"attempted to access tenant {target_tenant_id}"
            )

    @staticmethod
    def can_read_document(auth_context: AuthContext, document: Document) -> bool:
        """Check if caller is authorized to view the given document."""
        # Tenant isolation check
        if auth_context.tenant_id != document.tenant_id:
            return False

        # Classification clearance check
        if document.access_level > auth_context.max_clearance:
            return False

        # Department boundary check: Admin can access all departments
        if auth_context.role == UserRole.ADMIN:
            return True

        # General department documents are accessible tenant-wide
        if document.department == Department.GENERAL:
            return True

        # Otherwise, user must match document department
        return auth_context.department == document.department

    @staticmethod
    def enforce_read_document(auth_context: AuthContext, document: Document) -> None:
        """Raise AccessDeniedError if caller cannot read document."""
        if not AuthorizationPolicy.can_read_document(auth_context, document):
            msg = (
                f"Access denied to document '{document.title}' "
                f"(Classification: {document.access_level.name}, "
                f"Department: {document.department.value}) for user {auth_context.email}"
            )
            raise AccessDeniedError(msg)

    @staticmethod
    def can_read_chunk(auth_context: AuthContext, chunk: DocumentChunk) -> bool:
        """Check if caller is authorized to read a chunk in retrieval."""
        if auth_context.tenant_id != chunk.tenant_id:
            return False
        if chunk.access_level > auth_context.max_clearance:
            return False
        if auth_context.role == UserRole.ADMIN:
            return True
        if chunk.department == Department.GENERAL:
            return True
        return auth_context.department == chunk.department

    @staticmethod
    def can_upload_to_department(auth_context: AuthContext, department: Department) -> bool:
        """Check if caller can upload documents to a specific department."""
        if auth_context.role == UserRole.GUEST:
            return False
        if auth_context.role == UserRole.ADMIN:
            return True
        # Members and managers can upload to their own department or general
        return department in (auth_context.department, Department.GENERAL)

    @staticmethod
    def can_delete_document(auth_context: AuthContext, document: Document) -> bool:
        """Check if caller can delete a document."""
        if auth_context.tenant_id != document.tenant_id:
            return False
        if auth_context.role == UserRole.ADMIN:
            return True
        if auth_context.role == UserRole.MANAGER and document.department == auth_context.department:
            return True
        return False
