"""Ingestion application package."""

from src.application.ingestion.service import (
    DocumentIngestionService,
    IngestionResult,
)

__all__ = ["DocumentIngestionService", "IngestionResult"]
