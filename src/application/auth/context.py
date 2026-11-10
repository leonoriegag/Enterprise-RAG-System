"""Security context resolved for an authenticated request."""

from dataclasses import dataclass
from uuid import UUID

from src.domain.value_objects.access_level import AccessLevel
from src.domain.value_objects.department import Department
from src.domain.value_objects.role import UserRole


@dataclass(frozen=True)
class AuthContext:
    """Immutable server-side authorization context."""

    tenant_id: UUID
    user_id: UUID
    email: str
    role: UserRole
    department: Department
    max_clearance: AccessLevel

    @property
    def is_admin(self) -> bool:
        return self.role == UserRole.ADMIN

    @property
    def is_manager(self) -> bool:
        return self.role in (UserRole.ADMIN, UserRole.MANAGER)
