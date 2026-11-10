"""Ingestion status lifecycle states."""

from enum import StrEnum


class IngestionStatus(StrEnum):
    """Lifecycle states for ingested documents."""

    PENDING = "pending"
    PROCESSING = "processing"
    INDEXED = "indexed"
    FAILED = "failed"
