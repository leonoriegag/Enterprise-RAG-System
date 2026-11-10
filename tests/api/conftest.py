"""Pytest fixtures for FastAPI API testing with in-memory repositories and mocks."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any
from uuid import UUID, uuid4

import pytest
from httpx import ASGITransport, AsyncClient

from src.application.auth.service import PasswordService, TokenService
from src.application.ingestion.service import DocumentIngestionService
from src.application.rag.service import RAGService
from src.domain.entities.answer import RetrievedCandidate
from src.domain.entities.chunk import DocumentChunk
from src.domain.entities.document import Document
from src.domain.entities.tenant import Tenant
from src.domain.entities.user import User
from src.domain.interfaces.retrieval import RetrievalFilter
from src.domain.services.chunker import RecursiveTokenChunker
from src.domain.value_objects.access_level import AccessLevel
from src.domain.value_objects.department import Department
from src.domain.value_objects.ingestion_status import IngestionStatus
from src.domain.value_objects.role import UserRole
from src.infrastructure.documents.parsers.factory import ParserRegistry
from src.infrastructure.embeddings.mock_adapter import DeterministicMockEmbeddingAdapter
from src.infrastructure.llm.mock_adapter import DeterministicMockLLMAdapter
from src.interfaces.api.app import create_app
from src.interfaces.api.dependencies import (
    get_chunk_repository,
    get_db_session,
    get_document_repository,
    get_ingestion_service,
    get_rag_service,
    get_tenant_repository,
    get_tenant_session,
    get_user_repository,
)
from src.shared.config import Settings, get_settings


class MockTenantRepo:
    def __init__(self) -> None:
        self.tenants: dict[UUID, Tenant] = {}

    async def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        return self.tenants.get(tenant_id)

    async def get_by_slug(self, slug: str) -> Tenant | None:
        for t in self.tenants.values():
            if t.slug == slug:
                return t
        return None

    async def create(self, tenant: Tenant) -> Tenant:
        self.tenants[tenant.id] = tenant
        return tenant

    async def list_active(self) -> list[Tenant]:
        return [t for t in self.tenants.values() if t.is_active()]


class MockUserRepo:
    def __init__(self) -> None:
        self.users: dict[UUID, User] = {}

    async def get_by_id(self, user_id: UUID) -> User | None:
        return self.users.get(user_id)

    async def get_by_email(self, tenant_id: UUID, email: str) -> User | None:
        for u in self.users.values():
            if u.tenant_id == tenant_id and u.email == email.strip().lower():
                return u
        return None

    async def create(self, user: User) -> User:
        self.users[user.id] = user
        return user

    async def list_by_tenant(self, tenant_id: UUID) -> list[User]:
        return [u for u in self.users.values() if u.tenant_id == tenant_id]


class MockDocRepo:
    def __init__(self) -> None:
        self.docs: dict[UUID, Document] = {}

    async def get_by_id(self, document_id: UUID) -> Document | None:
        return self.docs.get(document_id)

    async def get_by_hash(self, tenant_id: UUID, content_hash: str) -> Document | None:
        for d in self.docs.values():
            if d.tenant_id == tenant_id and d.content_hash == content_hash:
                return d
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
        matches = [d for d in self.docs.values() if d.tenant_id == tenant_id]
        if department:
            matches = [d for d in matches if d.department.value == department.lower()]
        return matches[offset : offset + limit]


class MockChunkRepo:
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


class MockApiRetriever:
    def __init__(self, chunk_repo: MockChunkRepo, doc_repo: MockDocRepo) -> None:
        self.chunk_repo = chunk_repo
        self.doc_repo = doc_repo

    async def retrieve(
        self,
        query: str,
        filters: RetrievalFilter,
        top_k: int = 5,
    ) -> list[RetrievedCandidate]:
        results: list[RetrievedCandidate] = []
        for chunk in self.chunk_repo.chunks.values():
            if chunk.tenant_id != filters.tenant_id:
                continue
            if chunk.access_level > filters.max_clearance:
                continue
            if filters.target_department:
                if chunk.department != filters.target_department:
                    continue
            elif filters.role != UserRole.ADMIN:
                if chunk.department not in (filters.department, Department.GENERAL):
                    continue

            doc = await self.doc_repo.get_by_id(chunk.document_id)
            title = doc.title if doc else "Document"
            results.append(
                RetrievedCandidate(
                    chunk=chunk,
                    document_title=title,
                    rrf_score=0.08,
                    semantic_score=0.85,
                )
            )
        return results[:top_k]


@pytest.fixture
def test_settings() -> Settings:
    return Settings(
        APP_ENV="test",
        SECRET_KEY="test-insecure-secret-key-32-chars-minimum-for-testing",
        EMBEDDING_PROVIDER="mock",
        LLM_PROVIDER="mock",
    )


@pytest.fixture
def mock_tenant_repo() -> MockTenantRepo:
    return MockTenantRepo()


@pytest.fixture
def mock_user_repo() -> MockUserRepo:
    return MockUserRepo()


@pytest.fixture
def mock_doc_repo() -> MockDocRepo:
    return MockDocRepo()


@pytest.fixture
def mock_chunk_repo() -> MockChunkRepo:
    return MockChunkRepo()


@pytest.fixture
async def app_context(
    test_settings: Settings,
    mock_tenant_repo: MockTenantRepo,
    mock_user_repo: MockUserRepo,
    mock_doc_repo: MockDocRepo,
    mock_chunk_repo: MockChunkRepo,
) -> dict[str, Any]:
    # 1. Create ACME Tenant
    acme_tenant = Tenant(name="ACME Corporation", slug="acme")
    await mock_tenant_repo.create(acme_tenant)

    # 2. Create Second Tenant for Cross-Tenant tests
    other_tenant = Tenant(name="Other Corp", slug="other")
    await mock_tenant_repo.create(other_tenant)

    # 3. Create Users
    password_svc = PasswordService()
    admin_user = User(
        tenant_id=acme_tenant.id,
        email="admin@acme.corp",
        hashed_password=password_svc.hash_password("Password123!"),
        role=UserRole.ADMIN,
        department=Department.GENERAL,
    )
    hr_user = User(
        tenant_id=acme_tenant.id,
        email="hr@acme.corp",
        hashed_password=password_svc.hash_password("Password123!"),
        role=UserRole.MEMBER,
        department=Department.HR,
    )
    it_user = User(
        tenant_id=acme_tenant.id,
        email="it@acme.corp",
        hashed_password=password_svc.hash_password("Password123!"),
        role=UserRole.MEMBER,
        department=Department.IT,
    )
    other_user = User(
        tenant_id=other_tenant.id,
        email="user@other.corp",
        hashed_password=password_svc.hash_password("Password123!"),
        role=UserRole.MEMBER,
        department=Department.GENERAL,
    )
    await mock_user_repo.create(admin_user)
    await mock_user_repo.create(hr_user)
    await mock_user_repo.create(it_user)
    await mock_user_repo.create(other_user)

    # 4. Generate Tokens
    token_svc = TokenService(test_settings)
    admin_token = token_svc.create_access_token(admin_user)
    hr_token = token_svc.create_access_token(hr_user)
    it_token = token_svc.create_access_token(it_user)
    other_token = token_svc.create_access_token(other_user)

    # 5. Pre-seed Sample Documents
    leave_doc = Document(
        id=uuid4(),
        tenant_id=acme_tenant.id,
        title="Employee Leave Policy",
        file_path="leave_policy.md",
        mime_type="text/markdown",
        file_size_bytes=1024,
        content_hash="hash_leave_123",
        department=Department.HR,
        access_level=AccessLevel.INTERNAL,
        status=IngestionStatus.INDEXED,
    )
    await mock_doc_repo.create(leave_doc)

    leave_chunk = DocumentChunk(
        id=uuid4(),
        document_id=leave_doc.id,
        tenant_id=acme_tenant.id,
        chunk_index=0,
        content="Employees accrue 20 days paid time off per year. Carry over max 5 days.",
        department=Department.HR,
        access_level=AccessLevel.INTERNAL,
        section_header="Paid Time Off",
    )
    await mock_chunk_repo.save_chunks([leave_chunk])

    return {
        "acme_tenant": acme_tenant,
        "other_tenant": other_tenant,
        "admin_user": admin_user,
        "hr_user": hr_user,
        "it_user": it_user,
        "other_user": other_user,
        "admin_token": admin_token,
        "hr_token": hr_token,
        "it_token": it_token,
        "other_token": other_token,
        "leave_doc": leave_doc,
        "leave_chunk": leave_chunk,
    }


@pytest.fixture
async def client(
    test_settings: Settings,
    mock_tenant_repo: MockTenantRepo,
    mock_user_repo: MockUserRepo,
    mock_doc_repo: MockDocRepo,
    mock_chunk_repo: MockChunkRepo,
    app_context: dict[str, Any],
) -> AsyncGenerator[AsyncClient, None]:
    app = create_app(test_settings)

    # Setup RAG and Ingestion services with mocks
    retriever = MockApiRetriever(mock_chunk_repo, mock_doc_repo)
    mock_llm = DeterministicMockLLMAdapter()

    rag_service = RAGService(
        retriever=retriever,
        llm_provider=mock_llm,
        min_evidence_candidates=1,
    )

    ingestion_service = DocumentIngestionService(
        document_repo=mock_doc_repo,
        chunk_repo=mock_chunk_repo,
        parser_factory=ParserRegistry(),
        chunker=RecursiveTokenChunker(),
        embedding_provider=DeterministicMockEmbeddingAdapter(dimension=384),
    )

    # Dependency overrides
    app.dependency_overrides[get_settings] = lambda: test_settings
    app.dependency_overrides[get_tenant_repository] = lambda: mock_tenant_repo
    app.dependency_overrides[get_user_repository] = lambda: mock_user_repo
    app.dependency_overrides[get_document_repository] = lambda: mock_doc_repo
    app.dependency_overrides[get_chunk_repository] = lambda: mock_chunk_repo
    app.dependency_overrides[get_rag_service] = lambda: rag_service
    app.dependency_overrides[get_ingestion_service] = lambda: ingestion_service

    # Dummy session generators
    async def dummy_session():
        class DummySession:
            async def execute(self, *args, **kwargs):
                class DummyResult:
                    def scalar(self):
                        return 1

                return DummyResult()

            async def commit(self):
                pass

            async def rollback(self):
                pass

            async def close(self):
                pass

        yield DummySession()

    app.dependency_overrides[get_db_session] = dummy_session
    app.dependency_overrides[get_tenant_session] = dummy_session

    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac
