"""Chunker protocol and raw chunk contracts."""

from dataclasses import dataclass, field
from typing import Any, Protocol

from src.domain.interfaces.parsers import ParsedDocument


@dataclass
class RawChunk:
    """An un-indexed chunk with structural location metadata."""

    chunk_index: int
    content: str
    token_count: int
    page_number: int | None = None
    section_header: str | None = None
    character_start: int = 0
    character_end: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


class Chunker(Protocol):
    """Protocol for text chunking algorithms."""

    def chunk(
        self,
        document: ParsedDocument,
        chunk_size: int = 512,
        overlap: int = 64,
    ) -> list[RawChunk]:
        """Split parsed document into overlapping structure-aware chunks."""
        ...
