"""Retrieval and reranking protocols."""

from dataclasses import dataclass
from typing import Protocol
from uuid import UUID

from src.domain.entities.answer import RetrievedCandidate
from src.domain.value_objects.access_level import AccessLevel
from src.domain.value_objects.department import Department
from src.domain.value_objects.role import UserRole


@dataclass(frozen=True)
class RetrievalFilter:
    """Authorization and search filters passed to retrieval engines."""

    tenant_id: UUID
    user_id: UUID
    role: UserRole
    department: Department
    max_clearance: AccessLevel
    target_department: Department | None = None


class HybridRetriever(Protocol):
    """Protocol for hybrid semantic and lexical retrieval."""

    async def retrieve(
        self,
        query: str,
        filters: RetrievalFilter,
        top_k: int = 5,
    ) -> list[RetrievedCandidate]:
        """Execute hybrid search applying pre-retrieval authorization."""
        ...


class Reranker(Protocol):
    """Protocol for optional post-retrieval cross-encoder reranking."""

    async def rerank(
        self,
        query: str,
        candidates: list[RetrievedCandidate],
        top_n: int = 3,
    ) -> list[RetrievedCandidate]:
        """Rescore candidates with a cross-encoder model."""
        ...
