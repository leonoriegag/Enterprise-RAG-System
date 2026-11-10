"""Factory for resolving configured LLM providers."""

from __future__ import annotations

from src.domain.interfaces.llm import LLMProvider
from src.infrastructure.llm.mock_adapter import DeterministicMockLLMAdapter
from src.infrastructure.llm.openai_adapter import OpenAICompatibleLLMAdapter
from src.shared.config import Settings
from src.shared.logging import get_logger

logger = get_logger(__name__)


def get_llm_provider(settings: Settings) -> LLMProvider:
    """Return the configured LLM provider instance."""
    provider_type = settings.LLM_PROVIDER.lower()

    if provider_type == "mock":
        logger.info("Initializing DeterministicMockLLMAdapter (offline mode)")
        return DeterministicMockLLMAdapter()

    if provider_type == "openai":
        logger.info(f"Initializing OpenAICompatibleLLMAdapter (model={settings.OPENAI_MODEL})")
        return OpenAICompatibleLLMAdapter(settings)

    raise ValueError(
        f"Unknown LLM provider '{settings.LLM_PROVIDER}'. Supported: 'mock', 'openai'."
    )
