"""LLM provider protocol and generation contracts."""

from dataclasses import dataclass, field
from typing import Any, Protocol


@dataclass(frozen=True)
class GenerationResult:
    """Result of an LLM generation call."""

    content: str
    prompt_tokens: int = 0
    completion_tokens: int = 0
    model_name: str = ""
    finish_reason: str = "stop"
    raw_response: dict[str, Any] = field(default_factory=dict)

    @property
    def total_tokens(self) -> int:
        """Total tokens consumed (prompt + completion)."""
        return self.prompt_tokens + self.completion_tokens

    @property
    def did_abstain(self) -> bool:
        """Whether generation indicates abstention."""
        return self.finish_reason == "abstain"


class LLMProvider(Protocol):
    """Protocol for LLM response generation."""

    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> GenerationResult:
        """Generate response from system and user prompts."""
        ...

    @property
    def model_name(self) -> str:
        """Name of the underlying LLM."""
        ...
