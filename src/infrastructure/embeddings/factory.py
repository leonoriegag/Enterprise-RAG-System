"""Factory for creating configured embedding providers."""

from src.domain.interfaces.embeddings import EmbeddingProvider
from src.infrastructure.embeddings.mock_adapter import DeterministicMockEmbeddingAdapter
from src.infrastructure.embeddings.openai_adapter import OpenAICompatibleEmbeddingAdapter
from src.shared.config import Settings


def get_embedding_provider(settings: Settings) -> EmbeddingProvider:
    """Instantiate and return the configured embedding adapter."""
    if settings.EMBEDDING_PROVIDER == "mock":
        return DeterministicMockEmbeddingAdapter(
            dimension=settings.MOCK_EMBEDDING_DIM,
            model_name="mock-hash-embedding",
        )
    elif settings.EMBEDDING_PROVIDER == "openai":
        return OpenAICompatibleEmbeddingAdapter(
            api_key=settings.OPENAI_API_KEY,
            base_url=settings.OPENAI_BASE_URL,
            model=settings.OPENAI_EMBEDDING_MODEL,
            dimension=settings.OPENAI_EMBEDDING_DIM,
        )
    raise ValueError(f"Unknown embedding provider configured: '{settings.EMBEDDING_PROVIDER}'")
