"""Document management request and response schemas."""

from __future__ import annotations

from datetime import datetime
from uuid import UUID

from pydantic import BaseModel, Field


class DocumentUploadResponse(BaseModel):
    """Result of document upload and ingestion."""

    document_id: UUID
    title: str
    status: str
    chunks_created: int
    content_hash: str
    is_duplicate: bool = False
    message: str = "Document successfully ingested and indexed"


class DocumentDetailResponse(BaseModel):
    """Full document metadata and indexing status."""

    id: UUID
    tenant_id: UUID
    title: str
    filename: str
    mime_type: str
    department: str
    access_level: int
    status: str
    chunk_count: int
    content_hash: str
    created_at: datetime
    updated_at: datetime


class DocumentListResponse(BaseModel):
    """Paginated collection of documents."""

    total: int = Field(..., description="Total documents matching query")
    items: list[DocumentDetailResponse]


class DocumentDeleteResponse(BaseModel):
    """Result of document deletion."""

    document_id: UUID
    deleted: bool
    message: str


class DocumentReindexResponse(BaseModel):
    """Result of document re-indexing trigger."""

    document_id: UUID
    status: str
    message: str
