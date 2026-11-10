"""SQLAlchemy models for PostgreSQL with pgvector and full-text search."""

from datetime import UTC, datetime
from typing import Any
from uuid import UUID, uuid4

from pgvector.sqlalchemy import Vector
from sqlalchemy import (
    Boolean,
    DateTime,
    ForeignKey,
    Index,
    Integer,
    String,
    Text,
)
from sqlalchemy.dialects.postgresql import JSONB, TSVECTOR
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.infrastructure.database.base import Base


class TenantModel(Base):
    """PostgreSQL model for enterprise tenants."""

    __tablename__ = "tenants"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    slug: Mapped[str] = mapped_column(String(100), unique=True, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="active", nullable=False)
    settings: Mapped[dict[str, Any]] = mapped_column(JSONB, default=dict, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    users: Mapped[list["UserModel"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )
    documents: Mapped[list["DocumentModel"]] = relationship(
        back_populates="tenant", cascade="all, delete-orphan"
    )


class UserModel(Base):
    """PostgreSQL model for users with RBAC and department attributes."""

    __tablename__ = "users"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str] = mapped_column(String(50), nullable=False)
    department: Mapped[str] = mapped_column(String(50), nullable=False)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    tenant: Mapped["TenantModel"] = relationship(back_populates="users")

    __table_args__ = (Index("ix_users_tenant_email", "tenant_id", "email", unique=True),)


class DocumentModel(Base):
    """PostgreSQL model for documents with RLS support."""

    __tablename__ = "documents"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    file_path: Mapped[str] = mapped_column(String(512), nullable=False)
    mime_type: Mapped[str] = mapped_column(String(100), nullable=False)
    file_size_bytes: Mapped[int] = mapped_column(Integer, nullable=False)
    content_hash: Mapped[str] = mapped_column(String(64), nullable=False, index=True)
    department: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    access_level: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    doc_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, nullable=False
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        onupdate=lambda: datetime.now(UTC),
        nullable=False,
    )

    # Relationships
    tenant: Mapped["TenantModel"] = relationship(back_populates="documents")
    chunks: Mapped[list["DocumentChunkModel"]] = relationship(
        back_populates="document", cascade="all, delete-orphan"
    )

    __table_args__ = (Index("ix_docs_tenant_hash", "tenant_id", "content_hash", unique=True),)


class DocumentChunkModel(Base):
    """PostgreSQL model for chunks with vector embedding and tsvector."""

    __tablename__ = "document_chunks"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    document_id: Mapped[UUID] = mapped_column(
        ForeignKey("documents.id", ondelete="CASCADE"), nullable=False, index=True
    )
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    chunk_index: Mapped[int] = mapped_column(Integer, nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    department: Mapped[str] = mapped_column(String(50), nullable=False, index=True)
    access_level: Mapped[int] = mapped_column(Integer, nullable=False, index=True)

    page_number: Mapped[int | None] = mapped_column(Integer, nullable=True)
    section_header: Mapped[str | None] = mapped_column(String(255), nullable=True)
    token_count: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    character_start: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    character_end: Mapped[int] = mapped_column(Integer, default=0, nullable=False)

    # 384 or 1536 dim vector - configurable via dimension
    embedding: Mapped[list[float] | None] = mapped_column(Vector(None), nullable=True)
    fts_vector: Mapped[str | None] = mapped_column(TSVECTOR, nullable=True)
    chunk_metadata: Mapped[dict[str, Any]] = mapped_column(
        "metadata", JSONB, default=dict, nullable=False
    )

    # Relationships
    document: Mapped["DocumentModel"] = relationship(back_populates="chunks")

    __table_args__ = (
        Index("ix_chunks_tenant_dept_access", "tenant_id", "department", "access_level"),
        Index("ix_chunks_fts", "fts_vector", postgresql_using="gin"),
    )


class QueryAuditLogModel(Base):
    """Audit trail for RAG retrieval and generation requests."""

    __tablename__ = "query_audit_logs"

    id: Mapped[UUID] = mapped_column(primary_key=True, default=uuid4)
    tenant_id: Mapped[UUID] = mapped_column(
        ForeignKey("tenants.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id: Mapped[UUID] = mapped_column(
        ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    query_text: Mapped[str] = mapped_column(Text, nullable=False)
    chunks_retrieved: Mapped[int] = mapped_column(Integer, default=0, nullable=False)
    execution_time_ms: Mapped[float] = mapped_column(nullable=False)
    llm_provider: Mapped[str] = mapped_column(String(50), nullable=False)
    abstained: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(UTC),
        nullable=False,
    )
