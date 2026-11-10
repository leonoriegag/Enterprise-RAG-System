"""GroundedAnswer and RetrievedCandidate entities."""

from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from src.domain.entities.chunk import DocumentChunk
from src.domain.entities.citation import Citation


@dataclass
class RetrievedCandidate:
    """A scored candidate chunk returned by the retrieval engine."""

    chunk: DocumentChunk
    document_title: str
    semantic_score: float = 0.0
    lexical_score: float = 0.0
    rrf_score: float = 0.0
    rerank_score: float = 0.0

    @property
    def final_score(self) -> float:
        """Effective ranking score used for candidate ordering."""
        if self.rerank_score > 0:
            return self.rerank_score
        if self.rrf_score > 0:
            return self.rrf_score
        return max(self.semantic_score, self.lexical_score)


@dataclass
class GroundedAnswer:
    """Complete answer synthesized from authorized retrieved context."""

    query: str
    content: str
    citations: list[Citation]
    abstained: bool = False
    confidence_score: float = 0.0
    id: UUID = field(default_factory=uuid4)
    execution_metadata: dict[str, Any] = field(default_factory=dict)
    created_at: datetime = field(default_factory=lambda: datetime.now(UTC))
