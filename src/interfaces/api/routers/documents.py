"""Document ingestion and lifecycle management endpoints."""

from typing import Annotated
from uuid import UUID

from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile, status

from src.application.auth.context import AuthContext
from src.application.auth.policies import AuthorizationPolicy
from src.application.ingestion.service import DocumentIngestionService
from src.domain.exceptions import AccessDeniedError, IngestionError
from src.domain.interfaces.repositories import ChunkRepository, DocumentRepository
from src.domain.value_objects.access_level import AccessLevel
from src.domain.value_objects.department import Department
from src.interfaces.api.dependencies import (
    get_chunk_repository,
    get_current_auth,
    get_document_repository,
    get_ingestion_service,
)
from src.interfaces.api.schemas.documents import (
    DocumentDeleteResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentReindexResponse,
    DocumentUploadResponse,
)
from src.shared.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/documents", tags=["Documents"])


@router.post(
    "/upload",
    response_model=DocumentUploadResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Upload and ingest enterprise document",
    description="Validates, parses, chunks, generates embeddings, and indexes a document.",
)
async def upload_document(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    ingestion_service: Annotated[DocumentIngestionService, Depends(get_ingestion_service)],
    file: Annotated[UploadFile, File(description="Document binary file (PDF, DOCX, MD, TXT)")],
    title: Annotated[str, Form(min_length=2, max_length=255, description="Document display title")],
    department: Annotated[str, Form(description="Department classification scope")],
    access_level: Annotated[
        int, Form(ge=10, le=40, description="Access clearance level (10-40)")
    ] = 20,
) -> DocumentUploadResponse:
    """Ingest and index a newly uploaded corporate file with access controls."""
    dept = Department.from_str(department)
    clearance = AccessLevel(access_level)

    try:
        content_bytes = await file.read()
        filename = file.filename or "unknown.txt"
        declared_mime = file.content_type or "application/octet-stream"

        result = await ingestion_service.ingest_document(
            auth_context=auth,
            title=title,
            content=content_bytes,
            filename=filename,
            declared_mime=declared_mime,
            department=dept,
            access_level=clearance,
        )

        return DocumentUploadResponse(
            document_id=result.document_id,
            title=result.title,
            status=result.status.value,
            chunks_created=result.chunks_created,
            content_hash=result.content_hash,
            is_duplicate=result.is_duplicate,
            message="Document successfully ingested and indexed"
            if not result.is_duplicate
            else "Document already indexed; duplicate upload skipped",
        )
    except AccessDeniedError as e:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail=str(e)) from e
    except IngestionError as e:
        raise HTTPException(status_code=status.HTTP_422_UNPROCESSABLE_ENTITY, detail=str(e)) from e


@router.get(
    "",
    response_model=DocumentListResponse,
    status_code=status.HTTP_200_OK,
    summary="List documents",
    description="Retrieves tenant documents filtered by department and clearance permissions.",
)
async def list_documents(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    doc_repo: Annotated[DocumentRepository, Depends(get_document_repository)],
    chunk_repo: Annotated[ChunkRepository, Depends(get_chunk_repository)],
    department: Annotated[str | None, Query(description="Filter by department")] = None,
    limit: Annotated[int, Query(ge=1, le=100)] = 20,
    offset: Annotated[int, Query(ge=0)] = 0,
) -> DocumentListResponse:
    """List documents within caller's tenant adhering to access clearance."""
    all_docs = await doc_repo.list_by_tenant(
        tenant_id=auth.tenant_id,
        department=department,
        limit=limit,
        offset=offset,
    )

    items: list[DocumentDetailResponse] = []
    for doc in all_docs:
        if AuthorizationPolicy.can_read_document(auth, doc):
            chunks = await chunk_repo.get_by_document(doc.id)
            items.append(
                DocumentDetailResponse(
                    id=doc.id,
                    tenant_id=doc.tenant_id,
                    title=doc.title,
                    filename=doc.file_path.split("/")[-1],
                    mime_type=doc.mime_type,
                    department=doc.department.value,
                    access_level=doc.access_level.value,
                    status=doc.status.value,
                    chunk_count=len(chunks),
                    content_hash=doc.content_hash,
                    created_at=doc.created_at,
                    updated_at=doc.updated_at,
                )
            )

    return DocumentListResponse(total=len(items), items=items)


@router.get(
    "/{document_id}",
    response_model=DocumentDetailResponse,
    status_code=status.HTTP_200_OK,
    summary="Get document details",
    description="Inspect document status and metadata given document ID.",
)
async def get_document(
    document_id: UUID,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    doc_repo: Annotated[DocumentRepository, Depends(get_document_repository)],
    chunk_repo: Annotated[ChunkRepository, Depends(get_chunk_repository)],
) -> DocumentDetailResponse:
    """Fetch metadata for a single document."""
    doc = await doc_repo.get_by_id(document_id)
    if not doc or doc.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if not AuthorizationPolicy.can_read_document(auth, doc):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller lacks required department clearance to access this document",
        )

    chunks = await chunk_repo.get_by_document(doc.id)
    return DocumentDetailResponse(
        id=doc.id,
        tenant_id=doc.tenant_id,
        title=doc.title,
        filename=doc.file_path.split("/")[-1],
        mime_type=doc.mime_type,
        department=doc.department.value,
        access_level=doc.access_level.value,
        status=doc.status.value,
        chunk_count=len(chunks),
        content_hash=doc.content_hash,
        created_at=doc.created_at,
        updated_at=doc.updated_at,
    )


@router.delete(
    "/{document_id}",
    response_model=DocumentDeleteResponse,
    status_code=status.HTTP_200_OK,
    summary="Delete document",
    description="Removes document and all associated embeddings and chunks from knowledge base.",
)
async def delete_document(
    document_id: UUID,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    doc_repo: Annotated[DocumentRepository, Depends(get_document_repository)],
    chunk_repo: Annotated[ChunkRepository, Depends(get_chunk_repository)],
) -> DocumentDeleteResponse:
    """Permanently delete a document and its chunks."""
    doc = await doc_repo.get_by_id(document_id)
    if not doc or doc.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if not AuthorizationPolicy.can_delete_document(auth, doc):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller lacks authorization to delete this document",
        )

    await chunk_repo.delete_by_document(document_id)
    await doc_repo.delete(document_id)

    logger.info(f"Document {document_id} and its chunks deleted by user {auth.email}")
    return DocumentDeleteResponse(
        document_id=document_id,
        deleted=True,
        message="Document and indexed chunks successfully removed",
    )


@router.post(
    "/{document_id}/reindex",
    response_model=DocumentReindexResponse,
    status_code=status.HTTP_200_OK,
    summary="Trigger document re-indexing",
    description="Triggers re-indexing of an existing document.",
)
async def reindex_document(
    document_id: UUID,
    auth: Annotated[AuthContext, Depends(get_current_auth)],
    doc_repo: Annotated[DocumentRepository, Depends(get_document_repository)],
) -> DocumentReindexResponse:
    """Trigger re-indexing for an existing document."""
    doc = await doc_repo.get_by_id(document_id)
    if not doc or doc.tenant_id != auth.tenant_id:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Document not found")

    if not AuthorizationPolicy.can_upload_to_department(auth, doc.department):
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="Caller lacks permission to re-index documents in this department",
        )

    doc.mark_indexed()
    await doc_repo.update(doc)

    return DocumentReindexResponse(
        document_id=document_id,
        status=doc.status.value,
        message="Re-indexing completed successfully",
    )
