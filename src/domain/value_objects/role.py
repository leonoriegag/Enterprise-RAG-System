"""User roles in the multi-tenant RBAC model."""

from enum import StrEnum


class UserRole(StrEnum):
    """User roles defining privilege levels within a tenant."""

    ADMIN = "admin"
    MANAGER = "manager"
    MEMBER = "member"
    GUEST = "guest"

    @property
    def is_admin(self) -> bool:
        return self == UserRole.ADMIN

    @property
    def can_manage_documents(self) -> bool:
        return self in (UserRole.ADMIN, UserRole.MANAGER)
