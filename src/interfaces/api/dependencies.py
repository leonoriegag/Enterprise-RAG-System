"""FastAPI dependency injection providers for authentication, database, and services."""

from collections.abc import AsyncGenerator
from typing import Annotated

from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.ext.asyncio import AsyncSession

from src.application.auth.context import AuthContext
from src.application.auth.service import PasswordService, TokenService
from src.application.ingestion.service import DocumentIngestionService
from src.application.rag.service import RAGService
from src.domain.exceptions import AccessDeniedError
from src.domain.services.chunker import RecursiveTokenChunker
from src.domain.value_objects.role import UserRole
from src.infrastructure.database.repositories.chunk_repo import PostgresChunkRepository
from src.infrastructure.database.repositories.document_repo import PostgresDocumentRepository
from src.infrastructure.database.repositories.tenant_repo import PostgresTenantRepository
from src.infrastructure.database.repositories.user_repo import PostgresUserRepository
from src.infrastructure.database.session import get_session_factory, tenant_scoped_session
from src.infrastructure.documents.parsers.factory import ParserRegistry
from src.infrastructure.embeddings.factory import get_embedding_provider
from src.infrastructure.llm.factory import get_llm_provider
from src.infrastructure.retrieval.hybrid_retriever import PostgresHybridRetriever
from src.shared.config import Settings, get_settings

security = HTTPBearer(auto_error=False)


def get_token_service(settings: Annotated[Settings, Depends(get_settings)]) -> TokenService:
    """Return configured TokenService singleton instance."""
    return TokenService(settings)


def get_password_service() -> PasswordService:
    """Return cryptographic password hashing service."""
    return PasswordService()


async def get_db_session(
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncGenerator[AsyncSession, None]:
    """Yield open database session for non-tenant-specific operations."""
    factory = get_session_factory()
    async with factory() as session:
        try:
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()


async def get_current_auth(
    credentials: Annotated[HTTPAuthorizationCredentials | None, Depends(security)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
) -> AuthContext:
    """Validate bearer token from Authorization header and return immutable AuthContext."""
    if not credentials or not credentials.credentials:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or malformed Authorization header. Expected: Bearer <token>",
            headers={"WWW-Authenticate": "Bearer"},
        )

    try:
        return token_service.decode_token(credentials.credentials)
    except AccessDeniedError as e:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail=str(e),
            headers={"WWW-Authenticate": "Bearer"},
        ) from e


async def require_admin(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
) -> AuthContext:
    """Enforce that caller has administrative role in their tenant."""
    if auth.role != UserRole.ADMIN:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail=f"Operation requires ADMIN role. Current role: '{auth.role.value}'",
        )
    return auth


async def get_tenant_session(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> AsyncGenerator[AsyncSession, None]:
    """Yield tenant-scoped database session enforcing Row-Level Security (RLS)."""
    async with tenant_scoped_session(tenant_id=auth.tenant_id, settings=settings) as session:
        yield session


def get_tenant_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PostgresTenantRepository:
    """Provide tenant repository instance."""
    return PostgresTenantRepository(session)


def get_user_repository(
    session: Annotated[AsyncSession, Depends(get_db_session)],
) -> PostgresUserRepository:
    """Provide user repository instance."""
    return PostgresUserRepository(session)


def get_document_repository(
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> PostgresDocumentRepository:
    """Provide document repository scoped to caller's tenant."""
    return PostgresDocumentRepository(session)


def get_chunk_repository(
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
) -> PostgresChunkRepository:
    """Provide chunk repository scoped to caller's tenant."""
    return PostgresChunkRepository(session)


def get_ingestion_service(
    doc_repo: Annotated[PostgresDocumentRepository, Depends(get_document_repository)],
    chunk_repo: Annotated[PostgresChunkRepository, Depends(get_chunk_repository)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> DocumentIngestionService:
    """Construct DocumentIngestionService with configured adapters."""
    embedding_adapter = get_embedding_provider(settings)
    chunker = RecursiveTokenChunker(
        default_chunk_size=settings.CHUNK_SIZE_TOKENS,
        default_overlap=settings.CHUNK_OVERLAP_TOKENS,
    )
    return DocumentIngestionService(
        document_repo=doc_repo,
        chunk_repo=chunk_repo,
        parser_factory=ParserRegistry(),
        chunker=chunker,
        embedding_provider=embedding_adapter,
    )


def get_rag_service(
    session: Annotated[AsyncSession, Depends(get_tenant_session)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> RAGService:
    """Construct RAGService with hybrid retriever and configured LLM provider."""
    embedding_adapter = get_embedding_provider(settings)
    llm_adapter = get_llm_provider(settings)
    retriever = PostgresHybridRetriever(
        session=session,
        embedding_provider=embedding_adapter,
        rrf_k=settings.RRF_K_CONSTANT,
    )
    return RAGService(
        retriever=retriever,
        llm_provider=llm_adapter,
        default_top_k=settings.DEFAULT_TOP_K,
    )
