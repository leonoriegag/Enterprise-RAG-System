"""Document ingestion application service orchestrating parsing, chunking, and embedding."""

import hashlib
from dataclasses import dataclass, field
from typing import Any
from uuid import UUID

from src.application.auth.context import AuthContext
from src.application.auth.policies import AuthorizationPolicy
from src.domain.entities.chunk import DocumentChunk
from src.domain.entities.document import Document
from src.domain.exceptions import AccessDeniedError, DocumentNotFoundError, IngestionError
from src.domain.interfaces.chunker import Chunker
from src.domain.interfaces.embeddings import EmbeddingProvider
from src.domain.interfaces.parsers import DocumentParser
from src.domain.interfaces.repositories import ChunkRepository, DocumentRepository
from src.domain.services.validator import DocumentValidator
from src.domain.value_objects.access_level import AccessLevel
from src.domain.value_objects.department import Department
from src.domain.value_objects.ingestion_status import IngestionStatus
from src.shared.logging import get_logger

logger = get_logger(__name__)


@dataclass(frozen=True)
class IngestionResult:
    """Outcome of a document ingestion job."""

    document_id: UUID
    title: str
    status: IngestionStatus
    chunks_created: int
    content_hash: str
    is_duplicate: bool = False
    metadata: dict[str, Any] = field(default_factory=dict)


class DocumentIngestionService:
    """Orchestrates document validation, parsing, chunking, embedding, and storage."""

    def __init__(
        self,
        document_repo: DocumentRepository,
        chunk_repo: ChunkRepository,
        parser_factory: Any,  # ParserRegistry
        chunker: Chunker,
        embedding_provider: EmbeddingProvider,
        validator: DocumentValidator | None = None,
        batch_size: int = 32,
    ) -> None:
        self.document_repo = document_repo
        self.chunk_repo = chunk_repo
        self.parser_factory = parser_factory
        self.chunker = chunker
        self.embedding_provider = embedding_provider
        self.validator = validator or DocumentValidator()
        self.batch_size = batch_size

    async def ingest_document(
        self,
        auth_context: AuthContext,
        title: str,
        content: bytes,
        filename: str,
        declared_mime: str,
        department: Department,
        access_level: AccessLevel,
        extra_metadata: dict[str, Any] | None = None,
    ) -> IngestionResult:
        """Process and index an uploaded document file."""
        # 1. Authorization check: Can user upload to this department?
        if not AuthorizationPolicy.can_upload_to_department(auth_context, department):
            raise AccessDeniedError(
                f"User '{auth_context.email}' lacks permission to upload to '{department.value}'"
            )

        # 2. File validation (size, MIME type, magic bytes)
        val_result = self.validator.validate(content, filename, declared_mime)

        # 3. Content deduplication via SHA-256 digest
        content_hash = hashlib.sha256(content).hexdigest()
        existing_doc = await self.document_repo.get_by_hash(auth_context.tenant_id, content_hash)
        if existing_doc and existing_doc.status == IngestionStatus.INDEXED:
            logger.info(
                f"Document '{title}' already indexed with hash {content_hash}. Skipping re-parse."
            )
            return IngestionResult(
                document_id=existing_doc.id,
                title=existing_doc.title,
                status=existing_doc.status,
                chunks_created=0,
                content_hash=content_hash,
                is_duplicate=True,
                metadata={
                    "message": "Document already indexed",
                    "existing_id": str(existing_doc.id),
                },
            )

        # 4. Create initial document record with PENDING status
        doc_record = Document(
            tenant_id=auth_context.tenant_id,
            title=title,
            file_path=f"storage/{auth_context.tenant_id}/{filename}",
            mime_type=val_result.mime_type,
            file_size_bytes=val_result.file_size_bytes,
            content_hash=content_hash,
            department=department,
            access_level=access_level,
            status=IngestionStatus.PENDING,
            metadata=extra_metadata or {},
        )
        saved_doc = await self.document_repo.create(doc_record)

        try:
            # 5. Locate parser and extract structured content
            parser: DocumentParser = self.parser_factory.get_parser(val_result.mime_type, filename)
            parsed_doc = await parser.parse(content, filename)

            # 6. Generate overlapping structure-aware chunks
            raw_chunks = self.chunker.chunk(parsed_doc)
            if not raw_chunks:
                raise IngestionError(f"No extractable text content found in document '{filename}'.")

            # 7. Generate vector embeddings in batches
            chunk_texts = [rc.content for rc in raw_chunks]
            all_embeddings: list[list[float]] = []
            for i in range(0, len(chunk_texts), self.batch_size):
                batch = chunk_texts[i : i + self.batch_size]
                embeddings = await self.embedding_provider.embed_documents(batch)
                all_embeddings.extend(embeddings)

            # 8. Construct domain DocumentChunk entities
            domain_chunks: list[DocumentChunk] = []
            for rc, emb in zip(raw_chunks, all_embeddings, strict=False):
                chunk_entity = DocumentChunk(
                    document_id=saved_doc.id,
                    tenant_id=auth_context.tenant_id,
                    chunk_index=rc.chunk_index,
                    content=rc.content,
                    department=department,
                    access_level=access_level,
                    page_number=rc.page_number,
                    section_header=rc.section_header,
                    token_count=rc.token_count,
                    character_start=rc.character_start,
                    character_end=rc.character_end,
                    embedding=emb,
                    metadata=rc.metadata,
                )
                domain_chunks.append(chunk_entity)

            # 9. Persist chunks in repository
            await self.chunk_repo.save_chunks(domain_chunks)

            # 10. Update document status to INDEXED
            saved_doc.mark_indexed()
            saved_doc.metadata.update(parsed_doc.metadata)
            saved_doc.metadata["chunks_count"] = len(domain_chunks)
            await self.document_repo.update(saved_doc)

            logger.info(f"Ingested document '{title}' ({len(domain_chunks)} chunks created).")

            return IngestionResult(
                document_id=saved_doc.id,
                title=saved_doc.title,
                status=saved_doc.status,
                chunks_created=len(domain_chunks),
                content_hash=content_hash,
                is_duplicate=False,
                metadata=saved_doc.metadata,
            )

        except Exception as err:
            logger.error(f"Ingestion failed for document '{title}': {err}", exc_info=True)
            saved_doc.mark_failed(str(err))
            await self.document_repo.update(saved_doc)
            raise

    async def delete_document(self, auth_context: AuthContext, document_id: UUID) -> bool:
        """Cascade-delete document and all associated chunks/vectors."""
        doc = await self.document_repo.get_by_id(document_id)
        if not doc:
            raise DocumentNotFoundError(f"Document with ID {document_id} not found.")

        # Verify tenant isolation and delete permission
        AuthorizationPolicy.validate_tenant_access(auth_context, doc.tenant_id)
        if not AuthorizationPolicy.can_delete_document(auth_context, doc):
            raise AccessDeniedError(
                f"User '{auth_context.email}' lacks permission to delete document '{doc.title}'"
            )

        # Atomic cascade deletion
        await self.chunk_repo.delete_by_document(document_id)
        deleted = await self.document_repo.delete(document_id)
        logger.info(f"Deleted document '{doc.title}' and associated chunk vectors.")
        return deleted
