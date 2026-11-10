"""Unit tests for RAG application service."""

from unittest.mock import AsyncMock
from uuid import uuid4

import pytest

from src.application.auth.context import AuthContext
from src.application.rag.service import ABSTENTION_INSUFFICIENT_EVIDENCE, RAGService
from src.domain.entities.answer import RetrievedCandidate
from src.domain.entities.chunk import DocumentChunk
from src.domain.interfaces.llm import GenerationResult
from src.domain.value_objects.access_level import AccessLevel
from src.domain.value_objects.department import Department
from src.domain.value_objects.role import UserRole


def make_auth_context(
    role: UserRole = UserRole.MEMBER,
    dept: Department = Department.IT,
    clearance: AccessLevel = AccessLevel.INTERNAL,
) -> AuthContext:
    return AuthContext(
        tenant_id=uuid4(),
        user_id=uuid4(),
        email="developer@enterprise.internal",
        role=role,
        department=dept,
        max_clearance=clearance,
    )


def make_candidate(
    content: str,
    title: str = "IT Ops Guide",
    score: float = 0.05,
) -> RetrievedCandidate:
    chunk = DocumentChunk(
        document_id=uuid4(),
        tenant_id=uuid4(),
        chunk_index=0,
        content=content,
        department=Department.IT,
        access_level=AccessLevel.INTERNAL,
        section_header="Incident Response",
        page_number=3,
    )
    return RetrievedCandidate(
        chunk=chunk,
        document_title=title,
        rrf_score=score,
    )


@pytest.fixture
def mock_retriever() -> AsyncMock:
    return AsyncMock()


@pytest.fixture
def mock_llm() -> AsyncMock:
    llm = AsyncMock()
    llm.model_name = "mock-test-llm"
    llm.generate_response.return_value = GenerationResult(
        content="Production incidents require P1 escalation within 15 minutes [1].",
        prompt_tokens=40,
        completion_tokens=15,
        model_name="mock-test-llm",
        finish_reason="stop",
    )
    return llm


@pytest.mark.asyncio
async def test_rag_service_generates_grounded_answer(
    mock_retriever: AsyncMock,
    mock_llm: AsyncMock,
) -> None:
    candidate = make_candidate("Production incidents require P1 escalation within 15 minutes.")
    mock_retriever.retrieve.return_value = [candidate]

    service = RAGService(
        retriever=mock_retriever,
        llm_provider=mock_llm,
        min_evidence_candidates=1,
    )
    auth = make_auth_context()

    result = await service.ask("What is the escalation window for P1 incidents?", auth)

    assert result.did_abstain is False
    assert "P1 escalation" in result.answer_text
    assert len(result.citations) == 1
    assert result.citations[0].document_title == "IT Ops Guide"
    assert result.citations[0].citation_index == 1
    assert result.candidates_retrieved == 1
    assert result.candidates_used == 1
    assert result.model_name == "mock-test-llm"


@pytest.mark.asyncio
async def test_rag_service_abstains_when_no_candidates_retrieved(
    mock_retriever: AsyncMock,
    mock_llm: AsyncMock,
) -> None:
    mock_retriever.retrieve.return_value = []

    service = RAGService(
        retriever=mock_retriever,
        llm_provider=mock_llm,
        min_evidence_candidates=1,
    )
    auth = make_auth_context()

    result = await service.ask("What is our quantum computing policy?", auth)

    assert result.did_abstain is True
    assert result.answer_text == ABSTENTION_INSUFFICIENT_EVIDENCE
    assert result.citations == []
    mock_llm.generate_response.assert_not_called()


@pytest.mark.asyncio
async def test_rag_service_respects_confidence_threshold(
    mock_retriever: AsyncMock,
    mock_llm: AsyncMock,
) -> None:
    # Candidate score is 0.01, but threshold is 0.05
    candidate = make_candidate("Low relevance content.", score=0.01)
    mock_retriever.retrieve.return_value = [candidate]

    service = RAGService(
        retriever=mock_retriever,
        llm_provider=mock_llm,
        min_evidence_candidates=1,
    )
    auth = make_auth_context()

    result = await service.ask(
        query="Some obscure query",
        auth_context=auth,
        confidence_threshold=0.05,
    )

    assert result.did_abstain is True
    assert result.answer_text == ABSTENTION_INSUFFICIENT_EVIDENCE
    assert result.candidates_used == 0
    mock_llm.generate_response.assert_not_called()


@pytest.mark.asyncio
async def test_rag_service_strips_orphaned_citations(
    mock_retriever: AsyncMock,
    mock_llm: AsyncMock,
) -> None:
    candidate = make_candidate("Data retention policy is 7 years.")
    mock_retriever.retrieve.return_value = [candidate]

    # LLM hallucinates citation [5] when only 1 candidate was provided
    mock_llm.generate_response.return_value = GenerationResult(
        content="Retention is 7 years [1] according to internal standard [5].",
        prompt_tokens=40,
        completion_tokens=15,
        model_name="mock-test-llm",
        finish_reason="stop",
    )

    service = RAGService(
        retriever=mock_retriever,
        llm_provider=mock_llm,
    )
    auth = make_auth_context()

    result = await service.ask("What is data retention?", auth)

    assert result.did_abstain is False
    assert "[5]" not in result.answer_text
    assert "[1]" in result.answer_text
    assert len(result.citations) == 1
    assert 5 in result.metadata.get("orphaned_citations", [])
