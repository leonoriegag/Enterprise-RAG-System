"""Knowledge retrieval search endpoints."""

import time
from typing import Annotated

from fastapi import APIRouter, Depends, status
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.auth.context import AuthContext
from src.domain.interfaces.retrieval import RetrievalFilter
from src.domain.value_objects.department import Department
from src.infrastructure.embeddings.factory import get_embedding_provider
from src.infrastructure.retrieval.hybrid_retriever import PostgresHybridRetriever
from src.interfaces.api.dependencies import (
    get_current_auth,
    get_settings,
    get_tenant_session,
)
from src.interfaces.api.schemas.retrieval import SearchRequest, SearchResponse, SearchResultItem
from src.shared.config import Settings

router = APIRouter(prefix="/api/v1/retrieval", tags=["Retrieval"])


@router.post(
    "/search",
    response_model=SearchResponse,
    status_code=status.HTTP_200_OK,
    summary="Execute hybrid knowledge retrieval",
    description=(
        "Executes hybrid retrieval combining pgvector dense semantic search and "
        "PostgreSQL full-text search with Reciprocal Rank Fusion (RRF), enforcing "
        "pre-retrieval authorization filters."
    ),
)
async def search_knowledge(
    payload: SearchRequest,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> SearchResponse:
    """Retrieve relevant document chunks with pre-retrieval access control filters."""
    start_time = time.monotonic()

    target_dept = Department.from_str(payload.department) if payload.department else None

    filters = RetrievalFilter(
        tenant_id=auth.tenant_id,
        user_id=auth.user_id,
        role=auth.role,
        department=auth.department,
        max_clearance=auth.max_clearance,
        target_department=target_dept,
    )

    embedding_adapter = get_embedding_provider(settings)
    retriever = PostgresHybridRetriever(
        session=session,
        embedding_provider=embedding_adapter,
        rrf_k=settings.RRF_K_CONSTANT,
    )

    candidates = await retriever.retrieve(
        query=payload.query,
        filters=filters,
        top_k=payload.top_k,
    )

    execution_time_ms = (time.monotonic() - start_time) * 1000

    results = [
        SearchResultItem(
            chunk_id=c.chunk.id,
            document_id=c.chunk.document_id,
            document_title=c.document_title,
            content=c.chunk.content,
            department=c.chunk.department.value,
            access_level=c.chunk.access_level.value,
            section_header=c.chunk.section_header,
            score=c.final_score,
            rank=idx,
        )
        for idx, c in enumerate(candidates, start=1)
    ]

    return SearchResponse(
        query=payload.query,
        total_results=len(results),
        execution_time_ms=execution_time_ms,
        results=results,
    )
