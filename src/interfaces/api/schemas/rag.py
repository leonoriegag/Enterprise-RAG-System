"""RAG question-answering request and response schemas."""

from __future__ import annotations

from uuid import UUID

from pydantic import BaseModel, Field


class AskRequest(BaseModel):
    """User question for grounded retrieval-augmented generation."""

    question: str = Field(..., min_length=3, description="Natural language question to answer")
    department: str | None = Field(
        default=None, description="Target department scope (e.g. 'hr', 'it', 'general')"
    )
    top_k: int = Field(default=5, ge=1, le=20, description="Candidate evidence chunks to retrieve")
    confidence_threshold: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Minimum evidence threshold required"
    )


class CitationItem(BaseModel):
    """Traceable, verifiable source attribution citation."""

    citation_number: int = Field(..., description="1-based index referenced in generated answer")
    document_id: UUID
    document_title: str
    chunk_id: UUID
    page_number: int | None = None
    section_header: str | None = None
    quote_snippet: str | None = None


class AskResponse(BaseModel):
    """Grounded answer generated strictly from retrieved evidence with citations."""

    question: str
    answer: str = Field(..., description="Grounded response or honest abstention statement")
    abstained: bool = Field(
        ..., description="True if answer abstained due to lack of evidence or clearance"
    )
    confidence_score: float = Field(..., description="Evidence grounding confidence score")
    citations: list[CitationItem] = Field(
        default_factory=list, description="Verified source citations"
    )
    execution_time_ms: float
    model: str
    prompt_tokens: int
    completion_tokens: int
