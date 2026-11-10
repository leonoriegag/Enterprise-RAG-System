"""Unit tests for embedding adapters."""

import math

import pytest

from src.infrastructure.embeddings.factory import get_embedding_provider
from src.infrastructure.embeddings.mock_adapter import DeterministicMockEmbeddingAdapter
from src.shared.config import Settings


def cosine_similarity(v1: list[float], v2: list[float]) -> float:
    dot = sum(a * b for a, b in zip(v1, v2, strict=False))
    norm1 = math.sqrt(sum(a * a for a in v1))
    norm2 = math.sqrt(sum(b * b for b in v2))
    return dot / (norm1 * norm2) if norm1 > 0 and norm2 > 0 else 0.0


@pytest.mark.asyncio
async def test_deterministic_mock_embedding_properties() -> None:
    adapter = DeterministicMockEmbeddingAdapter(dimension=384)
    assert adapter.dimension == 384

    text_a = "Annual leave entitlement is 25 working days per calendar year."
    text_b = "Annual leave entitlement is 25 working days per calendar year."
    text_c = "Quantum computing superconductor qubit decoherence rates."

    emb_a = await adapter.embed_query(text_a)
    emb_b = await adapter.embed_query(text_b)
    emb_c = await adapter.embed_query(text_c)

    # 1. Dimension check
    assert len(emb_a) == 384

    # 2. Determinism check
    assert emb_a == emb_b

    # 3. Unit normalization check (sum of squares == 1.0)
    l2_norm = sum(x * x for x in emb_a)
    assert pytest.approx(l2_norm, abs=1e-5) == 1.0

    # 4. Semantic similarity: identical texts have similarity 1.0
    sim_identical = cosine_similarity(emb_a, emb_b)
    assert pytest.approx(sim_identical, abs=1e-5) == 1.0

    # 5. Semantic similarity: distinct text has lower similarity
    sim_distinct = cosine_similarity(emb_a, emb_c)
    assert sim_distinct < 0.95


@pytest.mark.asyncio
async def test_batch_embedding_matches_single() -> None:
    adapter = DeterministicMockEmbeddingAdapter(dimension=128)
    texts = ["Sentence one", "Sentence two", "Sentence three"]

    batch_embeddings = await adapter.embed_documents(texts)
    assert len(batch_embeddings) == 3

    for text, batch_emb in zip(texts, batch_embeddings, strict=False):
        single_emb = await adapter.embed_query(text)
        assert batch_emb == single_emb


def test_embedding_factory() -> None:
    mock_settings = Settings(EMBEDDING_PROVIDER="mock", MOCK_EMBEDDING_DIM=256)
    provider = get_embedding_provider(mock_settings)
    assert isinstance(provider, DeterministicMockEmbeddingAdapter)
    assert provider.dimension == 256
