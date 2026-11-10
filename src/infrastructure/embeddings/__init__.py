"""Embedding adapters package."""

from src.infrastructure.embeddings.factory import get_embedding_provider
from src.infrastructure.embeddings.mock_adapter import DeterministicMockEmbeddingAdapter
from src.infrastructure.embeddings.openai_adapter import OpenAICompatibleEmbeddingAdapter

__all__ = [
    "DeterministicMockEmbeddingAdapter",
    "OpenAICompatibleEmbeddingAdapter",
    "get_embedding_provider",
]
