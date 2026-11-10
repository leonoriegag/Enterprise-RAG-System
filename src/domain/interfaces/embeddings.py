"""Embedding provider protocol."""

from typing import Protocol


class EmbeddingProvider(Protocol):
    """Protocol for vector embedding generation."""

    async def embed_query(self, text: str) -> list[float]:
        """Generate vector embedding for a search query."""
        ...

    async def embed_documents(self, texts: list[str]) -> list[list[float]]:
        """Generate vector embeddings for a batch of document texts."""
        ...

    @property
    def dimension(self) -> int:
        """Vector dimension size."""
        ...

    @property
    def model_name(self) -> str:
        """Name or identifier of embedding model."""
        ...
