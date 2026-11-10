"""SQLAlchemy implementation of DocumentRepository."""

from uuid import UUID

from sqlalchemy import delete, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.document import Document
from src.domain.value_objects.access_level import AccessLevel
from src.domain.value_objects.department import Department
from src.domain.value_objects.ingestion_status import IngestionStatus
from src.infrastructure.database.models import DocumentModel


class PostgresDocumentRepository:
    """PostgreSQL repository for Document entity with RLS support."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, document_id: UUID) -> Document | None:
        stmt = select(DocumentModel).where(DocumentModel.id == document_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_hash(self, tenant_id: UUID, content_hash: str) -> Document | None:
        stmt = select(DocumentModel).where(
            DocumentModel.tenant_id == tenant_id,
            DocumentModel.content_hash == content_hash,
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def create(self, document: Document) -> Document:
        model = DocumentModel(
            id=document.id,
            tenant_id=document.tenant_id,
            title=document.title,
            file_path=document.file_path,
            mime_type=document.mime_type,
            file_size_bytes=document.file_size_bytes,
            content_hash=document.content_hash,
            department=document.department.value,
            access_level=document.access_level.value,
            status=document.status.value,
            doc_metadata=document.metadata,
            created_at=document.created_at,
            updated_at=document.updated_at,
        )
        self.session.add(model)
        await self.session.flush()
        return document

    async def update(self, document: Document) -> Document:
        stmt = select(DocumentModel).where(DocumentModel.id == document.id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        if model:
            model.title = document.title
            model.status = document.status.value
            model.doc_metadata = document.metadata
            model.updated_at = document.updated_at
            await self.session.flush()
        return document

    async def delete(self, document_id: UUID) -> bool:
        stmt = delete(DocumentModel).where(DocumentModel.id == document_id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        rowcount = getattr(result, "rowcount", 0)
        return bool(rowcount > 0)

    async def list_by_tenant(
        self,
        tenant_id: UUID,
        department: str | None = None,
        limit: int = 50,
        offset: int = 0,
    ) -> list[Document]:
        stmt = select(DocumentModel).where(DocumentModel.tenant_id == tenant_id)
        if department:
            stmt = stmt.where(DocumentModel.department == department)
        stmt = stmt.order_by(DocumentModel.created_at.desc()).limit(limit).offset(offset)
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    def _to_entity(self, model: DocumentModel) -> Document:
        return Document(
            id=model.id,
            tenant_id=model.tenant_id,
            title=model.title,
            file_path=model.file_path,
            mime_type=model.mime_type,
            file_size_bytes=model.file_size_bytes,
            content_hash=model.content_hash,
            department=Department.from_str(model.department),
            access_level=AccessLevel(model.access_level),
            status=IngestionStatus(model.status),
            metadata=model.doc_metadata,
            created_at=model.created_at,
            updated_at=model.updated_at,
        )
