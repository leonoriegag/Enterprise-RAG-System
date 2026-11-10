"""Security tests verifying absolute tenant isolation in retrieval and data access."""

from uuid import uuid4

import pytest

from src.application.auth.context import AuthContext
from src.application.auth.policies import AuthorizationPolicy
from src.application.rag.service import ABSTENTION_INSUFFICIENT_EVIDENCE, RAGService
from src.domain.entities.answer import RetrievedCandidate
from src.domain.entities.chunk import DocumentChunk
from src.domain.entities.document import Document
from src.domain.exceptions import CrossTenantViolationError
from src.domain.interfaces.llm import GenerationResult
from src.domain.interfaces.retrieval import RetrievalFilter
from src.domain.value_objects.access_level import AccessLevel
from src.domain.value_objects.department import Department
from src.domain.value_objects.role import UserRole


class MockIsolatedRetriever:
    """Mock retriever strictly enforcing tenant boundary in-memory."""

    def __init__(self, chunks: list[DocumentChunk]) -> None:
        self.chunks = chunks

    async def retrieve(
        self,
        query: str,
        filters: RetrievalFilter,
        top_k: int = 5,
    ) -> list[RetrievedCandidate]:
        # Pre-retrieval SQL WHERE equivalent: tenant_id = :tenant_id
        matching = [
            RetrievedCandidate(
                chunk=c,
                document_title="Sample Doc",
                rrf_score=0.05,
            )
            for c in self.chunks
            if c.tenant_id == filters.tenant_id
        ]
        return matching[:top_k]


class MockLLM:
    """Mock LLM provider."""

    @property
    def model_name(self) -> str:
        return "mock-security-llm"

    async def generate_response(
        self,
        system_prompt: str,
        user_prompt: str,
        temperature: float = 0.0,
        max_tokens: int = 1024,
    ) -> GenerationResult:
        return GenerationResult(
            content="Grounded response [1]",
            model_name="mock-security-llm",
        )


@pytest.mark.asyncio
async def test_cross_tenant_retrieval_returns_zero_results() -> None:
    """User from Tenant B must NEVER retrieve chunks belonging to Tenant A."""
    tenant_a = uuid4()
    tenant_b = uuid4()

    chunk_a = DocumentChunk(
        document_id=uuid4(),
        tenant_id=tenant_a,
        chunk_index=0,
        content="Confidential financial forecasts for Tenant A.",
        department=Department.FINANCE,
        access_level=AccessLevel.CONFIDENTIAL,
    )

    retriever = MockIsolatedRetriever([chunk_a])

    filter_b = RetrievalFilter(
        tenant_id=tenant_b,
        user_id=uuid4(),
        role=UserRole.ADMIN,  # Even an Admin of Tenant B!
        department=Department.FINANCE,
        max_clearance=AccessLevel.RESTRICTED,
    )

    results = await retriever.retrieve("financial forecasts", filter_b)
    assert len(results) == 0, "Security violation: Cross-tenant data leakage detected!"


@pytest.mark.asyncio
async def test_cross_tenant_rag_query_strictly_abstains() -> None:
    """RAGService query from a different tenant must abstain with zero citations."""
    tenant_a = uuid4()
    tenant_b = uuid4()

    chunk_a = DocumentChunk(
        document_id=uuid4(),
        tenant_id=tenant_a,
        chunk_index=0,
        content="Tenant A executive compensation matrix.",
        department=Department.HR,
        access_level=AccessLevel.INTERNAL,
    )

    rag = RAGService(
        retriever=MockIsolatedRetriever([chunk_a]),
        llm_provider=MockLLM(),
    )

    auth_b = AuthContext(
        tenant_id=tenant_b,
        user_id=uuid4(),
        email="attacker@tenant-b.com",
        role=UserRole.ADMIN,
        department=Department.HR,
        max_clearance=AccessLevel.RESTRICTED,
    )

    rag_result = await rag.ask("executive compensation", auth_b)

    assert rag_result.did_abstain is True
    assert rag_result.answer_text == ABSTENTION_INSUFFICIENT_EVIDENCE
    assert rag_result.citations == []
    assert rag_result.candidates_retrieved == 0


def test_cross_tenant_policy_validation_raises() -> None:
    """Direct policy validation must raise CrossTenantViolationError."""
    tenant_a = uuid4()
    tenant_b = uuid4()

    auth_a = AuthContext(
        tenant_id=tenant_a,
        user_id=uuid4(),
        email="user@tenant-a.com",
        role=UserRole.MEMBER,
        department=Department.IT,
        max_clearance=AccessLevel.INTERNAL,
    )

    doc_b = Document(
        tenant_id=tenant_b,
        title="Foreign Tenant Doc",
        file_path="storage/foreign.pdf",
        mime_type="application/pdf",
        file_size_bytes=1000,
        content_hash="abc",
        department=Department.IT,
        access_level=AccessLevel.INTERNAL,
    )

    with pytest.raises(CrossTenantViolationError):
        AuthorizationPolicy.validate_tenant_access(auth_a, doc_b.tenant_id)

    assert AuthorizationPolicy.can_read_document(auth_a, doc_b) is False
