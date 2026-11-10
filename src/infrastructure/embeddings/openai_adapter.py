"""OpenAI-compatible vector embedding adapter."""

from collections.abc import Sequence

import httpx

from src.domain.exceptions import ProviderUnavailableError


class OpenAICompatibleEmbeddingAdapter:
    """Embedding adapter compatible with OpenAI, Azure, and local Ollama/vLLM endpoints."""

    def __init__(
        self,
        api_key: str,
        base_url: str = "https://api.openai.com/v1",
        model: str = "text-embedding-3-small",
        dimension: int = 1536,
        timeout_seconds: float = 30.0,
    ) -> None:
        self._api_key = api_key
        self._base_url = base_url.rstrip("/")
        self._model = model
        self._dimension = dimension
        self._timeout = timeout_seconds

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model

    async def embed_query(self, text: str) -> list[float]:
        results = await self.embed_documents([text])
        if not results:
            raise ProviderUnavailableError("Empty embedding response returned by provider.")
        return results[0]

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        if not texts:
            return []

        url = f"{self._base_url}/embeddings"
        headers = {
            "Authorization": f"Bearer {self._api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "input": list(texts),
            "model": self._model,
        }

        try:
            async with httpx.AsyncClient(timeout=self._timeout) as client:
                response = await client.post(url, headers=headers, json=payload)
                if response.status_code != 200:
                    raise ProviderUnavailableError(
                        f"Embedding provider error (HTTP {response.status_code}): {response.text}"
                    )
                data = response.json()
                embeddings_data = data.get("data", [])
                # Sort by index to preserve input order
                embeddings_data.sort(key=lambda x: x.get("index", 0))
                return [item["embedding"] for item in embeddings_data]
        except httpx.RequestError as err:
            msg = f"Network error calling embedding provider: {err}"
            raise ProviderUnavailableError(msg) from err
