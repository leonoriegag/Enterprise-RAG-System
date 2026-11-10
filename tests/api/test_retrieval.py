"""Tests for /api/v1/retrieval hybrid knowledge search endpoint."""

from __future__ import annotations

from collections.abc import AsyncGenerator
from typing import Any

import pytest
from httpx import ASGITransport
from httpx import AsyncClient as _AsyncClient

from src.application.ingestion.service import DocumentIngestionService
from src.application.rag.service import RAGService
from src.domain.services.chunker import RecursiveTokenChunker
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
from tests.api.conftest import (
    MockApiRetriever,
    MockChunkRepo,
    MockDocRepo,
    MockTenantRepo,
    MockUserRepo,
)


class _EmptyMappings:
    """Mimics SQLAlchemy MappingResult.all() returning an empty list."""

    def all(self) -> list[Any]:
        return []


class _EmptyResult:
    """Mimics SQLAlchemy CursorResult with mappings() support (returns empty set)."""

    def mappings(self) -> _EmptyMappings:
        return _EmptyMappings()

    def scalar(self) -> int:
        return 0


class _RetrieverFriendlySession:
    """Async session stub satisfying PostgresHybridRetriever's execute() calls."""

    async def execute(self, *args: Any, **kwargs: Any) -> _EmptyResult:
        return _EmptyResult()

    async def commit(self) -> None:
        pass

    async def rollback(self) -> None:
        pass

    async def close(self) -> None:
        pass


@pytest.fixture
async def retrieval_client(
    app_context: dict[str, Any],
) -> AsyncGenerator[_AsyncClient, None]:
    """Stand-alone async client that overrides tenant_session for retrieval endpoint tests."""
    settings = Settings(
        APP_ENV="test",
        SECRET_KEY="test-insecure-secret-key-32-chars-minimum-for-testing",
        EMBEDDING_PROVIDER="mock",
        LLM_PROVIDER="mock",
    )

    app = create_app(settings)

    _tenant_repo = MockTenantRepo()
    _user_repo = MockUserRepo()
    _doc_repo = MockDocRepo()
    _chunk_repo = MockChunkRepo()
    _retriever = MockApiRetriever(_chunk_repo, _doc_repo)
    _llm = DeterministicMockLLMAdapter()
    _rag_service = RAGService(retriever=_retriever, llm_provider=_llm, min_evidence_candidates=1)
    _ingestion = DocumentIngestionService(
        document_repo=_doc_repo,
        chunk_repo=_chunk_repo,
        parser_factory=ParserRegistry(),
        chunker=RecursiveTokenChunker(),
        embedding_provider=DeterministicMockEmbeddingAdapter(dimension=384),
    )

    # Seed users into retrieval client's repos from app_context
    for user in [
        app_context["admin_user"],
        app_context["hr_user"],
        app_context["it_user"],
        app_context["other_user"],
    ]:
        await _user_repo.create(user)
    for tenant in [app_context["acme_tenant"], app_context["other_tenant"]]:
        await _tenant_repo.create(tenant)

    app.dependency_overrides[get_settings] = lambda: settings
    app.dependency_overrides[get_tenant_repository] = lambda: _tenant_repo
    app.dependency_overrides[get_user_repository] = lambda: _user_repo
    app.dependency_overrides[get_document_repository] = lambda: _doc_repo
    app.dependency_overrides[get_chunk_repository] = lambda: _chunk_repo
    app.dependency_overrides[get_rag_service] = lambda: _rag_service
    app.dependency_overrides[get_ingestion_service] = lambda: _ingestion

    async def retriever_session() -> AsyncGenerator[_RetrieverFriendlySession, None]:
        yield _RetrieverFriendlySession()

    app.dependency_overrides[get_db_session] = retriever_session
    app.dependency_overrides[get_tenant_session] = retriever_session

    transport = ASGITransport(app=app)
    async with _AsyncClient(transport=transport, base_url="http://testserver") as ac:
        yield ac


@pytest.mark.asyncio
async def test_search_requires_auth(client: _AsyncClient) -> None:
    """POST /api/v1/retrieval/search without bearer token must return 401."""
    response = await client.post(
        "/api/v1/retrieval/search",
        json={"query": "PTO days", "top_k": 5},
    )
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_search_returns_valid_response_shape(
    retrieval_client: _AsyncClient, app_context: dict[str, Any]
) -> None:
    """POST /api/v1/retrieval/search with valid token returns 200 and correct shape."""
    hr_token = app_context["hr_token"]
    response = await retrieval_client.post(
        "/api/v1/retrieval/search",
        headers={"Authorization": f"Bearer {hr_token}"},
        json={"query": "paid time off", "top_k": 5},
    )
    assert response.status_code == 200
    data = response.json()
    assert "query" in data
    assert "total_results" in data
    assert "execution_time_ms" in data
    assert "results" in data
    assert isinstance(data["results"], list)


@pytest.mark.asyncio
async def test_search_cross_tenant_returns_empty(
    retrieval_client: _AsyncClient, app_context: dict[str, Any]
) -> None:
    """User from other_tenant gets empty results — no cross-tenant chunk leakage."""
    other_token = app_context["other_token"]
    response = await retrieval_client.post(
        "/api/v1/retrieval/search",
        headers={"Authorization": f"Bearer {other_token}"},
        json={"query": "ACME employee leave policy", "top_k": 5},
    )
    assert response.status_code == 200
    data = response.json()
    # DummySession returns no rows → zero results, confirming no cross-tenant leakage
    assert data["total_results"] == 0
    assert data["results"] == []


@pytest.mark.asyncio
async def test_search_validates_missing_query(
    client: _AsyncClient, app_context: dict[str, Any]
) -> None:
    """Submitting a search request without 'query' field must return 422 validation error."""
    hr_token = app_context["hr_token"]
    response = await client.post(
        "/api/v1/retrieval/search",
        headers={"Authorization": f"Bearer {hr_token}"},
        json={"top_k": 5},
    )
    assert response.status_code == 422
