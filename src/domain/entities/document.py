"""Document entity representing an ingested corporate file."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from src.domain.value_objects.access_level import AccessLevel
from src.domain.value_objects.department import Department
from src.domain.value_objects.ingestion_status import IngestionStatus


@dataclass
class Document:
    """Document metadata and indexing state."""

    tenant_id: UUID
    title: str
    file_path: str
    mime_type: str
    file_size_bytes: int
    content_hash: str
    department: Department
    access_level: AccessLevel
    id: UUID = field(default_factory=uuid4)
    status: IngestionStatus = IngestionStatus.PENDING
    metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    updated_at: datetime = field(default_factory=lambda: datetime.now(UTC))

    def mark_indexed(self) -> None:
        self.status = IngestionStatus.INDEXED
        self.updated_at = datetime.now(UTC)

    def mark_failed(self, error_message: str) -> None:
        self.status = IngestionStatus.FAILED
        self.metadata["error"] = error_message
        self.updated_at = datetime.now(UTC)
