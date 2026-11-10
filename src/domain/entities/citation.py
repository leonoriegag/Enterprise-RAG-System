"""Citation entity representing verifiable evidence for an answer statement."""

from dataclasses import dataclass, field
from uuid import UUID, uuid4


@dataclass(frozen=True)
class Citation:
    """Explicit citation linking generated text to a source chunk."""

    document_id: UUID
    chunk_id: UUID
    citation_index: int
    document_title: str
    page_number: int | None = None
    section_header: str | None = None
    snippet: str = ""
    id: UUID = field(default_factory=uuid4)
