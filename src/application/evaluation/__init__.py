"""RAG offline evaluation and benchmarking framework."""

from src.application.evaluation.metrics import (
    abstention_accuracy,
    citation_coverage,
    mean_reciprocal_rank,
    ndcg_at_k,
    precision_at_k,
    recall_at_k,
)
from src.application.evaluation.runner import (
    EvaluationReport,
    EvaluationRunner,
    QueryEvaluationResult,
)

__all__ = [
    "EvaluationReport",
    "EvaluationRunner",
    "QueryEvaluationResult",
    "abstention_accuracy",
    "citation_coverage",
    "mean_reciprocal_rank",
    "ndcg_at_k",
    "precision_at_k",
    "recall_at_k",
]
