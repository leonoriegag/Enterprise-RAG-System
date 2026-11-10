"""OpenAI-compatible LLM adapter using HTTPX async client."""

from __future__ import annotations

from typing import Any

import httpx

from src.domain.interfaces.llm import GenerationResult
from src.shared.config import Settings
from src.shared.logging import get_logger

logger = get_logger(__name__)


class OpenAICompatibleLLMAdapter:
    """Async adapter for OpenAI-compatible /chat/completions API."""

    def __init__(self, settings: Settings) -> None:
        self.api_key = settings.OPENAI_API_KEY
        self.base_url = str(settings.OPENAI_BASE_URL).rstrip("/")
        self.model = settings.OPENAI_MODEL
        self.timeout = httpx.Timeout(60.0, connect=10.0)

    @property
    def model_name(self) -> str:
        """Name of the configured model."""
        return self.model

    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> GenerationResult:
        """Execute chat completion request against OpenAI-compatible endpoint."""
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }

        messages = [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_prompt},
        ]

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "max_tokens": max_tokens,
            "stream": False,
        }

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            response = await client.post(
                f"{self.base_url}/chat/completions",
                headers=headers,
                json=payload,
            )
            response.raise_for_status()
            data = response.json()

        choice = data["choices"][0]
        usage = data.get("usage", {})

        return GenerationResult(
            content=choice["message"]["content"],
            prompt_tokens=usage.get("prompt_tokens", 0),
            completion_tokens=usage.get("completion_tokens", 0),
            model_name=data.get("model", self.model),
            finish_reason=choice.get("finish_reason", "stop"),
            raw_response=data,
        )
