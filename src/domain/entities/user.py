"""User entity representing an authenticated user within a tenant."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from uuid import UUID, uuid4

from src.domain.value_objects.access_level import AccessLevel
from src.domain.value_objects.department import Department
from src.domain.value_objects.role import UserRole


@dataclass(frozen=True)
class User:
    """User account belonging to a specific tenant."""

    tenant_id: UUID
    email: str
    hashed_password: str
    role: UserRole
    department: Department
    id: UUID = field(default_factory=uuid4)
    is_active: bool = True
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    @property
    def max_access_level(self) -> AccessLevel:
        """Derive maximum document classification clearance based on role."""
        match self.role:
            case UserRole.ADMIN:
                return AccessLevel.RESTRICTED
            case UserRole.MANAGER:
                return AccessLevel.CONFIDENTIAL
            case UserRole.MEMBER:
                return AccessLevel.INTERNAL
            case UserRole.GUEST:
                return AccessLevel.PUBLIC
