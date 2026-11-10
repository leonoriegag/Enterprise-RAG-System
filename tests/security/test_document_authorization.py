"""Security tests verifying document classification clearance and department boundary rules."""

from uuid import uuid4

import pytest

from src.application.auth.context import AuthContext
from src.application.auth.policies import AuthorizationPolicy
from src.domain.entities.answer import RetrievedCandidate
from src.domain.entities.chunk import DocumentChunk
from src.domain.interfaces.retrieval import RetrievalFilter
from src.domain.value_objects.access_level import AccessLevel
from src.domain.value_objects.department import Department
from src.domain.value_objects.role import UserRole


class MockAuthAwareRetriever:
    """Mock retriever faithfully implementing pre-retrieval SQL WHERE logic."""

    def __init__(self, chunks: list[DocumentChunk]) -> None:
        self.chunks = chunks

    async def retrieve(
        self,
        query: str,
        filters: RetrievalFilter,
        top_k: int = 5,
    ) -> list[RetrievedCandidate]:
        results: list[RetrievedCandidate] = []
        for c in self.chunks:
            # 1. Tenant boundary
            if c.tenant_id != filters.tenant_id:
                continue

            # 2. Classification clearance
            if c.access_level > filters.max_clearance:
                continue

            # 3. Department boundary
            if filters.target_department is not None:
                if c.department != filters.target_department:
                    continue
            elif filters.role != UserRole.ADMIN:
                if c.department not in (filters.department, Department.GENERAL):
                    continue

            results.append(
                RetrievedCandidate(
                    chunk=c,
                    document_title="Auth Doc",
                    rrf_score=0.04,
                )
            )
        return results[:top_k]


@pytest.mark.asyncio
async def test_classification_clearance_enforcement() -> None:
    """User with clearance INTERNAL(20) must NOT retrieve CONFIDENTIAL(30) or RESTRICTED(40)."""
    tenant_id = uuid4()

    internal_chunk = DocumentChunk(
        document_id=uuid4(),
        tenant_id=tenant_id,
        chunk_index=0,
        content="General IT setup guide.",
        department=Department.IT,
        access_level=AccessLevel.INTERNAL,  # 20
    )
    confidential_chunk = DocumentChunk(
        document_id=uuid4(),
        tenant_id=tenant_id,
        chunk_index=1,
        content="Disaster Recovery failover keys.",
        department=Department.IT,
        access_level=AccessLevel.CONFIDENTIAL,  # 30
    )
    restricted_chunk = DocumentChunk(
        document_id=uuid4(),
        tenant_id=tenant_id,
        chunk_index=2,
        content="Executive severance packages.",
        department=Department.IT,
        access_level=AccessLevel.RESTRICTED,  # 40
    )

    retriever = MockAuthAwareRetriever([internal_chunk, confidential_chunk, restricted_chunk])

    # Caller has INTERNAL clearance
    filter_internal = RetrievalFilter(
        tenant_id=tenant_id,
        user_id=uuid4(),
        role=UserRole.MEMBER,
        department=Department.IT,
        max_clearance=AccessLevel.INTERNAL,
    )

    results = await retriever.retrieve("keys", filter_internal)
    retrieved_contents = [r.chunk.content for r in results]

    assert "General IT setup guide." in retrieved_contents
    assert "Disaster Recovery failover keys." not in retrieved_contents
    assert "Executive severance packages." not in retrieved_contents


@pytest.mark.asyncio
async def test_department_boundary_enforcement() -> None:
    """IT employee cannot access HR-specific chunks, but can access GENERAL chunks."""
    tenant_id = uuid4()

    it_chunk = DocumentChunk(
        document_id=uuid4(),
        tenant_id=tenant_id,
        chunk_index=0,
        content="IT Network Architecture.",
        department=Department.IT,
        access_level=AccessLevel.INTERNAL,
    )
    hr_chunk = DocumentChunk(
        document_id=uuid4(),
        tenant_id=tenant_id,
        chunk_index=1,
        content="HR Performance Review Ratings.",
        department=Department.HR,
        access_level=AccessLevel.INTERNAL,
    )
    general_chunk = DocumentChunk(
        document_id=uuid4(),
        tenant_id=tenant_id,
        chunk_index=2,
        content="Company Code of Conduct.",
        department=Department.GENERAL,
        access_level=AccessLevel.PUBLIC,
    )

    retriever = MockAuthAwareRetriever([it_chunk, hr_chunk, general_chunk])

    it_filter = RetrievalFilter(
        tenant_id=tenant_id,
        user_id=uuid4(),
        role=UserRole.MEMBER,
        department=Department.IT,
        max_clearance=AccessLevel.INTERNAL,
    )

    results = await retriever.retrieve("policy", it_filter)
    retrieved_contents = [r.chunk.content for r in results]

    assert "IT Network Architecture." in retrieved_contents
    assert "Company Code of Conduct." in retrieved_contents
    assert "HR Performance Review Ratings." not in retrieved_contents


def test_can_read_chunk_direct_policy_checks() -> None:
    """Verify AuthorizationPolicy.can_read_chunk logic."""
    tenant_id = uuid4()

    auth_employee = AuthContext(
        tenant_id=tenant_id,
        user_id=uuid4(),
        email="emp@acme.com",
        role=UserRole.MEMBER,
        department=Department.FINANCE,
        max_clearance=AccessLevel.INTERNAL,
    )

    # Allowed: same tenant, same dept, allowed clearance
    chunk_allowed = DocumentChunk(
        document_id=uuid4(),
        tenant_id=tenant_id,
        chunk_index=0,
        content="Finance guide.",
        department=Department.FINANCE,
        access_level=AccessLevel.INTERNAL,
    )
    assert AuthorizationPolicy.can_read_chunk(auth_employee, chunk_allowed) is True

    # Denied: same tenant, different dept (HR)
    chunk_diff_dept = DocumentChunk(
        document_id=uuid4(),
        tenant_id=tenant_id,
        chunk_index=0,
        content="HR guide.",
        department=Department.HR,
        access_level=AccessLevel.INTERNAL,
    )
    assert AuthorizationPolicy.can_read_chunk(auth_employee, chunk_diff_dept) is False

    # Denied: same dept, but clearance too high
    chunk_high_clearance = DocumentChunk(
        document_id=uuid4(),
        tenant_id=tenant_id,
        chunk_index=0,
        content="Confidential Finance audit.",
        department=Department.FINANCE,
        access_level=AccessLevel.CONFIDENTIAL,
    )
    assert AuthorizationPolicy.can_read_chunk(auth_employee, chunk_high_clearance) is False
