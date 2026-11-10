"""Initial schema, pgvector extension, and Row-Level Security (RLS) policies.

Revision ID: 001_initial_schema_and_rls
Revises: None
Create Date: 2026-11-09 23:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa
from pgvector.sqlalchemy import Vector
from sqlalchemy.dialects import postgresql

from alembic import op

# revision identifiers, used by Alembic.
revision: str = "001_initial_schema_and_rls"
down_revision: str | None = None
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    # 1. Enable required PostgreSQL extensions
    op.execute('CREATE EXTENSION IF NOT EXISTS "uuid-ossp";')
    op.execute('CREATE EXTENSION IF NOT EXISTS "vector";')

    # 2. Tenants table
    op.create_table(
        "tenants",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column("name", sa.String(255), nullable=False),
        sa.Column("slug", sa.String(100), nullable=False, unique=True),
        sa.Column("status", sa.String(50), nullable=False, server_default="active"),
        sa.Column(
            "settings",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_tenants_slug", "tenants", ["slug"], unique=True)

    # 3. Users table
    op.create_table(
        "users",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("hashed_password", sa.String(255), nullable=False),
        sa.Column("role", sa.String(50), nullable=False),
        sa.Column("department", sa.String(50), nullable=False),
        sa.Column("is_active", sa.Boolean(), nullable=False, server_default=sa.text("true")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_users_tenant_email", "users", ["tenant_id", "email"], unique=True)

    # 4. Documents table
    op.create_table(
        "documents",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("title", sa.String(255), nullable=False),
        sa.Column("file_path", sa.String(512), nullable=False),
        sa.Column("mime_type", sa.String(100), nullable=False),
        sa.Column("file_size_bytes", sa.Integer(), nullable=False),
        sa.Column("content_hash", sa.String(64), nullable=False),
        sa.Column("department", sa.String(50), nullable=False),
        sa.Column("access_level", sa.Integer(), nullable=False),
        sa.Column("status", sa.String(50), nullable=False, server_default="pending"),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
        sa.Column(
            "updated_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )
    op.create_index("ix_docs_tenant_hash", "documents", ["tenant_id", "content_hash"], unique=True)
    op.create_index("ix_docs_tenant_dept", "documents", ["tenant_id", "department"])

    # 5. Document Chunks table
    op.create_table(
        "document_chunks",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "document_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("documents.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("chunk_index", sa.Integer(), nullable=False),
        sa.Column("content", sa.Text(), nullable=False),
        sa.Column("department", sa.String(50), nullable=False),
        sa.Column("access_level", sa.Integer(), nullable=False),
        sa.Column("page_number", sa.Integer(), nullable=True),
        sa.Column("section_header", sa.String(255), nullable=True),
        sa.Column("token_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("character_start", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("character_end", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("embedding", Vector(None), nullable=True),
        sa.Column("fts_vector", postgresql.TSVECTOR(), nullable=True),
        sa.Column(
            "metadata",
            postgresql.JSONB(astext_type=sa.Text()),
            nullable=False,
            server_default="{}",
        ),
    )
    op.create_index(
        "ix_chunks_tenant_dept_access",
        "document_chunks",
        ["tenant_id", "department", "access_level"],
    )
    op.create_index("ix_chunks_fts", "document_chunks", ["fts_vector"], postgresql_using="gin")

    # 6. Query Audit Logs table
    op.create_table(
        "query_audit_logs",
        sa.Column("id", postgresql.UUID(as_uuid=True), primary_key=True),
        sa.Column(
            "tenant_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("tenants.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column(
            "user_id",
            postgresql.UUID(as_uuid=True),
            sa.ForeignKey("users.id", ondelete="CASCADE"),
            nullable=False,
        ),
        sa.Column("query_text", sa.Text(), nullable=False),
        sa.Column("chunks_retrieved", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("execution_time_ms", sa.Float(), nullable=False),
        sa.Column("llm_provider", sa.String(50), nullable=False),
        sa.Column("abstained", sa.Boolean(), nullable=False, server_default=sa.text("false")),
        sa.Column(
            "created_at",
            sa.DateTime(timezone=True),
            nullable=False,
            server_default=sa.func.now(),
        ),
    )

    # 7. Enable and Force Row-Level Security (RLS) on multi-tenant tables
    op.execute("ALTER TABLE documents ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE documents FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY tenant_isolation_documents ON documents
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
    """)

    op.execute("ALTER TABLE document_chunks ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE document_chunks FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY tenant_isolation_chunks ON document_chunks
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
    """)

    op.execute("ALTER TABLE query_audit_logs ENABLE ROW LEVEL SECURITY;")
    op.execute("ALTER TABLE query_audit_logs FORCE ROW LEVEL SECURITY;")
    op.execute("""
        CREATE POLICY tenant_isolation_audit ON query_audit_logs
            FOR ALL
            USING (tenant_id = NULLIF(current_setting('app.current_tenant_id', true), '')::uuid);
    """)


def downgrade() -> None:
    # Drop RLS policies
    op.execute("DROP POLICY IF EXISTS tenant_isolation_audit ON query_audit_logs;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_chunks ON document_chunks;")
    op.execute("DROP POLICY IF EXISTS tenant_isolation_documents ON documents;")

    op.drop_table("query_audit_logs")
    op.drop_table("document_chunks")
    op.drop_table("documents")
    op.drop_table("users")
    op.drop_table("tenants")
