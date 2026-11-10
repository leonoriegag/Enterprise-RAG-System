"""Knowledge retrieval search schemas."""

from __future__ import annotations

from typing import Literal
from uuid import UUID

from pydantic import BaseModel, Field


class SearchRequest(BaseModel):
    """Knowledge search query parameters."""

    query: str = Field(..., min_length=2, description="Natural language search or keyword query")
    department: str | None = Field(
        default=None,
        description="Optional target department filter (restricted by caller clearance)",
    )
    top_k: int = Field(default=5, ge=1, le=50, description="Maximum candidate chunks to retrieve")
    mode: Literal["hybrid", "semantic", "lexical"] = Field(
        default="hybrid", description="Retrieval fusion strategy"
    )


class SearchResultItem(BaseModel):
    """Individual retrieved knowledge chunk candidate."""

    chunk_id: UUID
    document_id: UUID
    document_title: str
    content: str
    department: str
    access_level: int
    section_header: str | None
    score: float
    rank: int


class SearchResponse(BaseModel):
    """Search execution result envelope."""

    query: str
    total_results: int
    execution_time_ms: float
    results: list[SearchResultItem]
