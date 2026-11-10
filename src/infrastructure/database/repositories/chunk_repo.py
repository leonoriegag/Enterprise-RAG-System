"""SQLAlchemy implementation of ChunkRepository for vector and lexical search."""

from uuid import UUID

from sqlalchemy import delete, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.chunk import DocumentChunk
from src.domain.value_objects.access_level import AccessLevel
from src.domain.value_objects.department import Department
from src.infrastructure.database.models import DocumentChunkModel


class PostgresChunkRepository:
    """PostgreSQL repository for document chunk embeddings and FTS vectors."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def save_chunks(self, chunks: list[DocumentChunk]) -> int:
        if not chunks:
            return 0

        models: list[DocumentChunkModel] = []
        for chunk in chunks:
            model = DocumentChunkModel(
                id=chunk.id,
                document_id=chunk.document_id,
                tenant_id=chunk.tenant_id,
                chunk_index=chunk.chunk_index,
                content=chunk.content,
                department=chunk.department.value,
                access_level=chunk.access_level.value,
                page_number=chunk.page_number,
                section_header=chunk.section_header,
                token_count=chunk.token_count,
                character_start=chunk.character_start,
                character_end=chunk.character_end,
                embedding=chunk.embedding,
                fts_vector=func.to_tsvector("english", chunk.content),
                chunk_metadata=chunk.metadata,
            )
            models.append(model)

        self.session.add_all(models)
        await self.session.flush()
        return len(models)

    async def delete_by_document(self, document_id: UUID) -> int:
        stmt = delete(DocumentChunkModel).where(DocumentChunkModel.document_id == document_id)
        result = await self.session.execute(stmt)
        await self.session.flush()
        rowcount = getattr(result, "rowcount", 0)
        return int(rowcount)

    async def get_by_id(self, chunk_id: UUID) -> DocumentChunk | None:
        stmt = select(DocumentChunkModel).where(DocumentChunkModel.id == chunk_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_document(self, document_id: UUID) -> list[DocumentChunk]:
        stmt = (
            select(DocumentChunkModel)
            .where(DocumentChunkModel.document_id == document_id)
            .order_by(DocumentChunkModel.chunk_index)
        )
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    def _to_entity(self, model: DocumentChunkModel) -> DocumentChunk:
        return DocumentChunk(
            id=model.id,
            document_id=model.document_id,
            tenant_id=model.tenant_id,
            chunk_index=model.chunk_index,
            content=model.content,
            department=Department.from_str(model.department),
            access_level=AccessLevel(model.access_level),
            page_number=model.page_number,
            section_header=model.section_header,
            token_count=model.token_count,
            character_start=model.character_start,
            character_end=model.character_end,
            embedding=list(model.embedding) if model.embedding is not None else None,
            metadata=model.chunk_metadata,
        )
