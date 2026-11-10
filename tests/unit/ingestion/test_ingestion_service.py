"""Unit tests for DocumentIngestionService with in-memory repositories."""

from uuid import UUID, uuid4

import pytest

from src.application.auth.context import AuthContext
from src.application.ingestion.service import DocumentIngestionService
from src.domain.entities.chunk import DocumentChunk
from src.domain.entities.document import Document
from src.domain.exceptions import AccessDeniedError
from src.domain.services.chunker import RecursiveTokenChunker
from src.domain.value_objects.access_level import AccessLevel
from src.domain.value_objects.department import Department
from src.domain.value_objects.ingestion_status import IngestionStatus
from src.domain.value_objects.role import UserRole
from src.infrastructure.documents.parsers.factory import ParserRegistry
from src.infrastructure.embeddings.mock_adapter import DeterministicMockEmbeddingAdapter


class InMemoryDocumentRepo:
    """In-memory mock for DocumentRepository."""

    def __init__(self) -> None:
        self.docs: dict[UUID, Document] = {}

    async def get_by_id(self, document_id: UUID) -> Document | None:
        return self.docs.get(document_id)

    async def get_by_hash(self, tenant_id: UUID, content_hash: str) -> Document | None:
        for doc in self.docs.values():
            if doc.tenant_id == tenant_id and doc.content_hash == content_hash:
                return doc
        return None

    async def create(self, document: Document) -> Document:
        self.docs[document.id] = document
        return document

    async def update(self, document: Document) -> Document:
        self.docs[document.id] = document
        return document

    async def delete(self, document_id: UUID) -> bool:
        return self.docs.pop(document_id, None) is not None

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        department: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Document]:
        return [d for d in self.docs.values() if d.tenant_id == tenant_id]


class InMemoryChunkRepo:
    """In-memory mock for ChunkRepository."""

    def __init__(self) -> None:
        self.chunks: dict[UUID, DocumentChunk] = {}

    async def save_chunks(self, chunks: list[DocumentChunk]) -> int:
        for c in chunks:
            self.chunks[c.id] = c
        return len(chunks)

    async def delete_by_document(self, document_id: UUID) -> int:
        to_del = [cid for cid, c in self.chunks.items() if c.document_id == document_id]
        for cid in to_del:
            del self.chunks[cid]
        return len(to_del)

    async def get_by_id(self, chunk_id: UUID) -> DocumentChunk | None:
        return self.chunks.get(chunk_id)

    async def get_by_document(self, document_id: UUID) -> list[DocumentChunk]:
        return [c for c in self.chunks.values() if c.document_id == document_id]


@pytest.fixture
def auth_context():
    return AuthContext(
        tenant_id=uuid4(),
        user_id=uuid4(),
        email="hr.manager@acme.com",
        role=UserRole.MANAGER,
        department=Department.HR,
        max_clearance=AccessLevel.CONFIDENTIAL,
    )


@pytest.fixture
def ingestion_service():
    doc_repo = InMemoryDocumentRepo()
    chunk_repo = InMemoryChunkRepo()
    parser_factory = ParserRegistry()
    chunker = RecursiveTokenChunker(default_chunk_size=100, default_overlap=20)
    embedding_provider = DeterministicMockEmbeddingAdapter(dimension=128)

    service = DocumentIngestionService(
        document_repo=doc_repo,
        chunk_repo=chunk_repo,
        parser_factory=parser_factory,
        chunker=chunker,
        embedding_provider=embedding_provider,
    )
    return service, doc_repo, chunk_repo


@pytest.mark.asyncio
async def test_full_document_ingestion_lifecycle(auth_context, ingestion_service) -> None:
    service, doc_repo, chunk_repo = ingestion_service

    content = (
        b"# ACME HR Remote Work Guidelines\n\n"
        b"Employees may work remotely up to two days per week with manager approval.\n\n"
        b"Core collaboration hours are 10:00 to 15:00 local time."
    )

    result = await service.ingest_document(
        auth_context=auth_context,
        title="Remote Work Guidelines",
        content=content,
        filename="remote_work.md",
        declared_mime="text/markdown",
        department=Department.HR,
        access_level=AccessLevel.INTERNAL,
    )

    assert result.status == IngestionStatus.INDEXED
    assert result.chunks_created > 0
    assert result.is_duplicate is False

    # Verify document in repo
    saved_doc = await doc_repo.get_by_id(result.document_id)
    assert saved_doc is not None
    assert saved_doc.status == IngestionStatus.INDEXED

    # Verify chunks in repo
    saved_chunks = await chunk_repo.get_by_document(result.document_id)
    assert len(saved_chunks) == result.chunks_created
    for chunk in saved_chunks:
        assert chunk.embedding is not None
        assert len(chunk.embedding) == 128
        assert chunk.department == Department.HR
        assert chunk.access_level == AccessLevel.INTERNAL


@pytest.mark.asyncio
async def test_ingestion_deduplication(auth_context, ingestion_service) -> None:
    service, doc_repo, chunk_repo = ingestion_service

    content = b"ACME Operational Safety Standards and Protocols."

    # First ingestion
    res1 = await service.ingest_document(
        auth_context=auth_context,
        title="Safety Standards",
        content=content,
        filename="safety.txt",
        declared_mime="text/plain",
        department=Department.HR,
        access_level=AccessLevel.INTERNAL,
    )
    assert res1.is_duplicate is False

    # Second ingestion of identical content
    res2 = await service.ingest_document(
        auth_context=auth_context,
        title="Safety Standards Copy",
        content=content,
        filename="safety.txt",
        declared_mime="text/plain",
        department=Department.HR,
        access_level=AccessLevel.INTERNAL,
    )
    assert res2.is_duplicate is True
    assert res2.document_id == res1.document_id
    assert res2.chunks_created == 0


@pytest.mark.asyncio
async def test_unauthorized_upload_rejected(auth_context, ingestion_service) -> None:
    service, _, _ = ingestion_service

    content = b"Engineering Architecture Blueprints"

    # HR Manager trying to upload to Engineering department
    with pytest.raises(AccessDeniedError, match="lacks permission to upload"):
        await service.ingest_document(
            auth_context=auth_context,
            title="Eng Blueprints",
            content=content,
            filename="blueprints.txt",
            declared_mime="text/plain",
            department=Department.ENGINEERING,
            access_level=AccessLevel.CONFIDENTIAL,
        )


@pytest.mark.asyncio
async def test_cascade_deletion(auth_context, ingestion_service) -> None:
    service, doc_repo, chunk_repo = ingestion_service

    content = b"Confidential HR Audit notes."
    res = await service.ingest_document(
        auth_context=auth_context,
        title="HR Audit",
        content=content,
        filename="audit.txt",
        declared_mime="text/plain",
        department=Department.HR,
        access_level=AccessLevel.CONFIDENTIAL,
    )

    chunks_before = await chunk_repo.get_by_document(res.document_id)
    assert len(chunks_before) > 0

    # Delete document
    deleted = await service.delete_document(auth_context, res.document_id)
    assert deleted is True

    # Chunks and doc must be gone
    doc_after = await doc_repo.get_by_id(res.document_id)
    assert doc_after is None
    chunks_after = await chunk_repo.get_by_document(res.document_id)
    assert len(chunks_after) == 0
