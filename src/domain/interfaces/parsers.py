"""Document parser protocol and parsed representations."""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass
class ParsedSection:
    """A structural section of a parsed document."""

    content: str
    page_number: int | None = None
    section_header: str | None = None
    character_start: int = 0
    character_end: int = 0


@dataclass
class ParsedDocument:
    """Standardized representation of a parsed file."""

    filename: str
    mime_type: str
    full_text: str
    sections: list[ParsedSection] = field(default_factory=list)
    metadata: dict[str, Any] = field(default_factory=dict)


class DocumentParser(Protocol):
    """Protocol for format-specific document extractors."""

    def can_parse(self, mime_type: str) -> bool:
        """Return True if this parser supports the given MIME type."""
        ...

    async def parse(self, content: bytes, filename: str) -> ParsedDocument:
        """Extract structured text and section boundaries from file bytes."""
        ...
