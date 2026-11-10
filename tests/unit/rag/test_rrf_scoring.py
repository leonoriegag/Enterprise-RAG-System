"""Unit tests for Reciprocal Rank Fusion (RRF) ranking algorithm."""

import pytest

RRF_K = 60


def rrf_score(rank: int, k: int = RRF_K) -> float:
    """Calculate single list RRF score: 1 / (k + rank)."""
    return 1.0 / (k + rank)


def fuse_ranks(
    semantic_ranks: dict[str, int],
    lexical_ranks: dict[str, int],
    k: int = RRF_K,
) -> dict[str, float]:
    """Fuse rank distributions from two search lists."""
    scores: dict[str, float] = {}
    for doc_id, rank in semantic_ranks.items():
        scores[doc_id] = scores.get(doc_id, 0.0) + rrf_score(rank, k)
    for doc_id, rank in lexical_ranks.items():
        scores[doc_id] = scores.get(doc_id, 0.0) + rrf_score(rank, k)
    return scores


def test_rrf_score_decreases_monotonically_with_rank() -> None:
    """Better ranks must produce strictly higher reciprocal rank scores."""
    assert rrf_score(1) > rrf_score(2)
    assert rrf_score(2) > rrf_score(5)
    assert rrf_score(5) > rrf_score(50)


def test_rrf_score_bounded_above_by_k_plus_one() -> None:
    """Rank 1 score must equal exactly 1 / (k + 1)."""
    assert rrf_score(1, k=60) == pytest.approx(1.0 / 61.0)
    assert rrf_score(1, k=60) < (1.0 / 60.0)


def test_dual_appearance_boosts_fused_score() -> None:
    """Candidates appearing in both semantic and lexical lists should score higher."""
    sem = {"chunk_A": 1, "chunk_B": 2}
    lex = {"chunk_A": 1, "chunk_C": 1}

    fused = fuse_ranks(sem, lex)

    # chunk_A appeared rank 1 in both -> must beat single-list rank 1 (chunk_C)
    assert fused["chunk_A"] > fused["chunk_C"]
    # chunk_A must beat chunk_B
    assert fused["chunk_A"] > fused["chunk_B"]
    # chunk_C (rank 1 lex) beats chunk_B (rank 2 sem)
    assert fused["chunk_C"] > fused["chunk_B"]


def test_fused_scores_are_ordered_deterministically() -> None:
    """Candidates with strong balanced ranks should outrank heavily skewed low ranks."""
    sem = {"X": 1, "Y": 2, "Z": 20}
    lex = {"Z": 1, "Y": 2, "X": 30}

    fused = fuse_ranks(sem, lex)
    sorted_items = sorted(fused.items(), key=lambda kv: kv[1], reverse=True)
    top_id = sorted_items[0][0]

    # Y is rank 2 in BOTH -> 1/62 + 1/62 = 2/62 = 0.03225
    # X is 1/61 + 1/90 = 0.01639 + 0.01111 = 0.0275
    # Z is 1/80 + 1/61 = 0.0125 + 0.01639 = 0.02889
    # Therefore Y wins!
    assert top_id == "Y"


def test_rrf_k_parameter_sensitivity() -> None:
    """Lower k makes the score much more sensitive to differences in top ranks."""
    delta_low_k = rrf_score(1, k=10) - rrf_score(2, k=10)
    delta_high_k = rrf_score(1, k=100) - rrf_score(2, k=100)
    assert delta_low_k > delta_high_k
