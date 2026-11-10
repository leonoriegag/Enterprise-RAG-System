"""Deterministic mock embedding adapter for reproducible offline development and CI."""

import hashlib
import math
import struct
from collections.abc import Sequence


class DeterministicMockEmbeddingAdapter:
    """Generates reproducible unit-normalized vector embeddings without external API calls."""

    def __init__(self, dimension: int = 384, model_name: str = "deterministic-mock-v1") -> None:
        self._dimension = dimension
        self._model_name = model_name

    @property
    def dimension(self) -> int:
        return self._dimension

    @property
    def model_name(self) -> str:
        return self._model_name

    async def embed_query(self, text: str) -> list[float]:
        """Embed single query string deterministically."""
        return self._compute_embedding(text)

    async def embed_documents(self, texts: Sequence[str]) -> list[list[float]]:
        """Embed batch of document strings deterministically."""
        return [self._compute_embedding(t) for t in texts]

    def _compute_embedding(self, text: str) -> list[float]:
        """Generate a dense unit vector from text tokens using SHA-256 projections."""
        if not text:
            # Return zero vector with slight perturbation on index 0 to avoid zero-division
            vec = [0.0] * self._dimension
            vec[0] = 1.0
            return vec

        vector = [0.0] * self._dimension
        words = text.lower().split()

        if not words:
            vec = [0.0] * self._dimension
            vec[0] = 1.0
            return vec

        for word in words:
            # Hash word into 32 bytes
            digest = hashlib.sha256(word.encode("utf-8")).digest()
            # Distribute entropy across the vector dimensions
            for i in range(self._dimension):
                offset = (i * 4) % 28
                val_bytes = digest[offset : offset + 4]
                val = struct.unpack(">i", val_bytes)[0] / (2**31)
                vector[i] += val

        # L2 Unit Normalization (sum(v_i^2) = 1.0)
        norm = math.sqrt(sum(x * x for x in vector))
        if norm > 1e-12:
            vector = [x / norm for x in vector]
        else:
            vector[0] = 1.0

        return vector
