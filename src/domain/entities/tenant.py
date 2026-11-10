"""Tenant entity representing an isolated enterprise organization."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4


@dataclass(frozen=True)
class Tenant:
    """Enterprise Tenant isolation boundary."""

    name: str
    slug: str
    id: UUID = field(default_factory=uuid4)
    status: str = "active"
    settings: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def is_active(self) -> bool:
        return self.status == "active"
