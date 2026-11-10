"""Unit tests for offline evaluation metrics."""

import pytest

from src.application.evaluation.metrics import (
    abstention_accuracy,
    citation_coverage,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)


def test_recall_at_k() -> None:
    ground_truth = ["doc_A", "doc_B"]
    retrieved = ["doc_A", "doc_C", "doc_D"]

    # 1 of 2 retrieved in top-3
    assert recall_at_k(retrieved, ground_truth, k=3) == 0.5
    # Both retrieved in top-5
    assert recall_at_k(["doc_A", "doc_B", "doc_C"], ground_truth, k=5) == 1.0
    # Empty ground truth handled cleanly
    assert recall_at_k([], [], k=5) == 1.0
    assert recall_at_k(["doc_X"], [], k=5) == 0.0


def test_precision_at_k() -> None:
    ground_truth = ["doc_A", "doc_B"]
    retrieved = ["doc_A", "doc_C", "doc_B", "doc_D"]

    # 1 of 2 in top-2
    assert precision_at_k(retrieved, ground_truth, k=2) == 0.5
    # 2 of 4 in top-4
    assert precision_at_k(retrieved, ground_truth, k=4) == 0.5


def test_mean_reciprocal_rank() -> None:
    ground_truth = ["doc_target"]

    # First position -> RR = 1.0
    assert mean_reciprocal_rank(["doc_target", "doc_other"], ground_truth) == 1.0
    # Second position -> RR = 0.5
    assert mean_reciprocal_rank(["doc_other", "doc_target"], ground_truth) == 0.5
    # Fourth position -> RR = 0.25
    assert mean_reciprocal_rank(["a", "b", "c", "doc_target"], ground_truth) == 0.25
    # Not found -> RR = 0.0
    assert mean_reciprocal_rank(["a", "b", "c"], ground_truth) == 0.0


def test_ndcg_at_k() -> None:
    ground_truth = ["doc_1", "doc_2"]

    # Perfect ranking: both ground truth items at top
    assert ndcg_at_k(["doc_1", "doc_2", "doc_3"], ground_truth, k=3) == pytest.approx(1.0)
    # Reversed ranking: non-ideal ordering
    ndcg_suboptimal = ndcg_at_k(["doc_3", "doc_1", "doc_2"], ground_truth, k=3)
    assert 0.0 < ndcg_suboptimal < 1.0


def test_citation_coverage() -> None:
    # Answerable query with citations
    assert citation_coverage(citations_count=2, did_abstain=False, is_answerable=True) == 1.0
    # Answerable query without citations (failure)
    assert citation_coverage(citations_count=0, did_abstain=False, is_answerable=True) == 0.0
    # Unanswerable query that abstained (success)
    assert citation_coverage(citations_count=0, did_abstain=True, is_answerable=False) == 1.0
    # Unanswerable query that failed to abstain
    assert citation_coverage(citations_count=1, did_abstain=False, is_answerable=False) == 0.0


def test_abstention_accuracy() -> None:
    preds = [True, False, True, False]
    expected = [True, False, False, False]
    # 3 matches out of 4 = 0.75
    assert abstention_accuracy(preds, expected) == 0.75
