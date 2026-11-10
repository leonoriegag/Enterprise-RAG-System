"""Unit tests for domain entities and value objects."""

from uuid import uuid4

from src.domain.entities.answer import GroundedAnswer, RetrievedCandidate
from src.domain.entities.chunk import DocumentChunk
from src.domain.entities.citation import Citation
from src.domain.entities.document import Document
from src.domain.entities.tenant import Tenant
from src.domain.entities.user import User
from src.domain.value_objects.access_level import AccessLevel
from src.domain.value_objects.department import Department
from src.domain.value_objects.ingestion_status import IngestionStatus
from src.domain.value_objects.role import UserRole


def test_tenant_creation_and_activity() -> None:
    tenant = Tenant(name="ACME Corp", slug="acme-corp")
    assert tenant.is_active() is True
    assert tenant.name == "ACME Corp"
    assert tenant.slug == "acme-corp"


def test_user_role_clearance_mapping() -> None:
    tenant_id = uuid4()
    admin = User(
        tenant_id=tenant_id,
        email="admin@acme.com",
        hashed_password="hash",
        role=UserRole.ADMIN,
        department=Department.SECURITY,
    )
    assert admin.max_access_level == AccessLevel.RESTRICTED

    manager = User(
        tenant_id=tenant_id,
        email="manager@acme.com",
        hashed_password="hash",
        role=UserRole.MANAGER,
        department=Department.HR,
    )
    assert manager.max_access_level == AccessLevel.CONFIDENTIAL

    member = User(
        tenant_id=tenant_id,
        email="member@acme.com",
        hashed_password="hash",
        role=UserRole.MEMBER,
        department=Department.ENGINEERING,
    )
    assert member.max_access_level == AccessLevel.INTERNAL

    guest = User(
        tenant_id=tenant_id,
        email="guest@acme.com",
        hashed_password="hash",
        role=UserRole.GUEST,
        department=Department.GENERAL,
    )
    assert guest.max_access_level == AccessLevel.PUBLIC


def test_document_lifecycle_transitions() -> None:
    tenant_id = uuid4()
    doc = Document(
        tenant_id=tenant_id,
        title="Leave Policy",
        file_path="/storage/leave.pdf",
        mime_type="application/pdf",
        file_size_bytes=1024,
        content_hash="abc123hash",
        department=Department.HR,
        access_level=AccessLevel.INTERNAL,
    )
    assert doc.status == IngestionStatus.PENDING

    doc.mark_indexed()
    assert doc.status == IngestionStatus.INDEXED

    doc.mark_failed("Corrupt PDF stream")
    assert doc.status == IngestionStatus.FAILED
    assert doc.metadata["error"] == "Corrupt PDF stream"


def test_document_chunk_and_citation() -> None:
    tenant_id = uuid4()
    doc_id = uuid4()
    chunk = DocumentChunk(
        document_id=doc_id,
        tenant_id=tenant_id,
        chunk_index=0,
        content="Employees are granted 25 days of annual leave.",
        department=Department.HR,
        access_level=AccessLevel.INTERNAL,
        page_number=3,
        section_header="3.1 Annual Entitlement",
    )
    assert chunk.page_number == 3
    assert chunk.section_header == "3.1 Annual Entitlement"

    citation = Citation(
        document_id=doc_id,
        chunk_id=chunk.id,
        citation_index=1,
        document_title="ACME Leave Policy",
        page_number=3,
        section_header="3.1 Annual Entitlement",
        snippet=chunk.content[:40],
    )
    assert citation.citation_index == 1
    assert citation.page_number == 3


def test_retrieved_candidate_score_resolution() -> None:
    tenant_id = uuid4()
    doc_id = uuid4()
    chunk = DocumentChunk(
        document_id=doc_id,
        tenant_id=tenant_id,
        chunk_index=0,
        content="Test content",
        department=Department.GENERAL,
        access_level=AccessLevel.PUBLIC,
    )

    candidate = RetrievedCandidate(
        chunk=chunk,
        document_title="Doc A",
        semantic_score=0.82,
        lexical_score=0.60,
    )
    # Without RRF or rerank, takes max
    assert candidate.final_score == 0.82

    candidate.rrf_score = 0.032
    assert candidate.final_score == 0.032

    candidate.rerank_score = 0.95
    assert candidate.final_score == 0.95


def test_grounded_answer_creation() -> None:
    answer = GroundedAnswer(
        query="What is the leave entitlement?",
        content="Employees receive 25 days [1].",
        citations=[],
        confidence_score=0.91,
    )
    assert answer.abstained is False
    assert answer.confidence_score == 0.91
