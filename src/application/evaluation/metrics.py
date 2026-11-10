"""Evaluation metrics for RAG retrieval, generation quality, and security."""

from __future__ import annotations

import math


def recall_at_k(retrieved: list[str], ground_truth: list[str], k: int = 5) -> float:
    """
    Calculate Recall@K: proportion of ground-truth relevant documents found in top-K.

    If ground_truth is empty (e.g. unanswerable query):
    returns 1.0 if retrieved is empty, else 0.0.
    """
    if not ground_truth:
        return 1.0 if not retrieved else 0.0

    top_k = retrieved[:k]
    gt_set = set(ground_truth)
    hits = sum(1 for item in top_k if item in gt_set)
    return hits / len(gt_set)


def precision_at_k(retrieved: list[str], ground_truth: list[str], k: int = 5) -> float:
    """
    Calculate Precision@K: proportion of top-K retrieved documents that are relevant.

    If top-K is empty:
    returns 1.0 if ground_truth is empty, else 0.0.
    """
    top_k = retrieved[:k]
    if not top_k:
        return 1.0 if not ground_truth else 0.0

    gt_set = set(ground_truth)
    hits = sum(1 for item in top_k if item in gt_set)
    return hits / len(top_k)


def mean_reciprocal_rank(retrieved: list[str], ground_truth: list[str]) -> float:
    """
    Calculate Reciprocal Rank (RR): reciprocal of the rank of the first relevant document.

    Returns 0.0 if no ground-truth document appears in retrieved list.
    """
    if not ground_truth:
        return 1.0 if not retrieved else 0.0

    gt_set = set(ground_truth)
    for rank, item in enumerate(retrieved, start=1):
        if item in gt_set:
            return 1.0 / rank
    return 0.0


def ndcg_at_k(retrieved: list[str], ground_truth: list[str], k: int = 5) -> float:
    """Calculate Normalized Discounted Cumulative Gain at K (nDCG@K) with binary relevance."""
    if not ground_truth:
        return 1.0 if not retrieved else 0.0

    top_k = retrieved[:k]
    gt_set = set(ground_truth)

    dcg = 0.0
    for rank, item in enumerate(top_k, start=1):
        if item in gt_set:
            dcg += 1.0 / math.log2(rank + 1)

    # Ideal DCG: best possible ordering (all ground truth items at top)
    idcg = 0.0
    ideal_hits = min(len(gt_set), k)
    for rank in range(1, ideal_hits + 1):
        idcg += 1.0 / math.log2(rank + 1)

    if idcg == 0.0:
        return 0.0
    return dcg / idcg


def citation_coverage(citations_count: int, did_abstain: bool, is_answerable: bool) -> float:
    """
    Verify citation attribution coverage.

    Answerable queries require at least one verified citation (1.0).
    Unanswerable queries that honestly abstain receive 1.0 coverage.
    """
    if is_answerable:
        return 1.0 if citations_count > 0 and not did_abstain else 0.0
    return 1.0 if did_abstain else 0.0


def abstention_accuracy(
    predicted_abstentions: list[bool],
    expected_abstentions: list[bool],
) -> float:
    """Calculate accuracy of abstention decisions across all test cases."""
    if not expected_abstentions:
        return 1.0

    matches = sum(
        1
        for pred, exp in zip(predicted_abstentions, expected_abstentions, strict=False)
        if pred == exp
    )
    return matches / len(expected_abstentions)
