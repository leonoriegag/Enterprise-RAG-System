"""DocumentChunk entity with vector and lexical properties."""

from dataclasses import dataclass, field
from typing import Any
from uuid import UUID, uuid4

from src.domain.value_objects.access_level import AccessLevel
from src.domain.value_objects.department import Department


@dataclass
class DocumentChunk:
    """A granular chunk of an indexed document."""

    document_id: UUID
    tenant_id: UUID
    chunk_index: int
    content: str
    department: Department
    access_level: AccessLevel
    id: UUID = field(default_factory=uuid4)
    page_number: int | None = None
    section_header: str | None = None
    token_count: int = 0
    character_start: int = 0
    character_end: int = 0
    embedding: list[float] | None = None
    fts_vector: str | None = None
    metadata: dict[str, Any] = field(default_factory=dict)
