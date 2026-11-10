"""RAG question-answering endpoints with verifiable citations and abstention."""

from typing import Annotated

from fastapi import APIRouter, Depends, status

from src.application.auth.context import AuthContext
from src.application.rag.service import RAGService
from src.domain.value_objects.department import Department
from src.interfaces.api.dependencies import get_current_auth, get_rag_service
from src.interfaces.api.schemas.rag import AskRequest, AskResponse, CitationItem
from src.shared.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/rag", tags=["RAG"])


@router.post(
    "/ask",
    response_model=AskResponse,
    status_code=status.HTTP_200_OK,
    summary="Ask enterprise knowledge question",
    description=(
        "Answers user queries using strictly grounded retrieval evidence, enforcing "
        "department boundaries, clearance ceilings, and honest abstention."
    ),
)
async def ask_question(
    payload: AskRequest,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    rag_service: Annotated[RAGService, Depends(get_rag_service)],
) -> AskResponse:
    """Execute end-to-end RAG pipeline with grounded citations."""
    target_dept = Department.from_str(payload.department) if payload.department else None

    rag_result = await rag_service.ask(
        query=payload.question,
        auth_context=auth,
        target_department=target_dept,
        top_k=payload.top_k,
        confidence_threshold=payload.confidence_threshold,
    )

    citations = [
        CitationItem(
            citation_number=c.citation_index,
            document_id=c.document_id,
            document_title=c.document_title,
            chunk_id=c.chunk_id,
            page_number=c.page_number,
            section_header=c.section_header,
            quote_snippet=c.snippet if c.snippet else None,
        )
        for c in rag_result.citations
    ]

    return AskResponse(
        question=payload.question,
        answer=rag_result.answer_text,
        abstained=rag_result.did_abstain,
        confidence_score=rag_result.answer.confidence_score,
        citations=citations,
        execution_time_ms=rag_result.execution_time_ms,
        model=rag_result.model_name,
        prompt_tokens=rag_result.prompt_tokens,
        completion_tokens=rag_result.completion_tokens,
    )
