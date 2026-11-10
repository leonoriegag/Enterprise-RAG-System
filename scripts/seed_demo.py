"""ACME Enterprise knowledge base seeding script.

Initializes database schema, creates the ACME Enterprise tenant, provisions
demonstration user accounts with varying roles and departments, and ingests
the 8 ACME portfolio knowledge base documents.
"""

from __future__ import annotations

import asyncio
from dataclasses import dataclass
from pathlib import Path

from src.application.auth.context import AuthContext
from src.application.auth.service import PasswordService
from src.application.ingestion.service import DocumentIngestionService
from src.domain.entities.tenant import Tenant
from src.domain.entities.user import User
from src.domain.services.chunker import RecursiveTokenChunker
from src.domain.value_objects.access_level import AccessLevel
from src.domain.value_objects.department import Department
from src.domain.value_objects.role import UserRole
from src.infrastructure.database.models import Base
from src.infrastructure.database.repositories.chunk_repo import PostgresChunkRepository
from src.infrastructure.database.repositories.document_repo import PostgresDocumentRepository
from src.infrastructure.database.repositories.tenant_repo import PostgresTenantRepository
from src.infrastructure.database.repositories.user_repo import PostgresUserRepository
from src.infrastructure.database.session import (
    get_engine,
    get_session_factory,
    tenant_scoped_session,
)
from src.infrastructure.documents.parsers.factory import ParserRegistry
from src.infrastructure.embeddings.factory import get_embedding_provider
from src.shared.config import get_settings
from src.shared.logging import configure_logging, get_logger

logger = get_logger("seed")


@dataclass(frozen=True)
class ACMEDocSpec:
    """Specification for an ACME demonstration document."""

    file: str
    title: str
    department: Department
    access_level: AccessLevel


ACME_DOCUMENTS: list[ACMEDocSpec] = [
    ACMEDocSpec(
        file="general_code_of_conduct.md",
        title="ACME Corporation — Global Code of Business Conduct and Ethics",
        department=Department.GENERAL,
        access_level=AccessLevel.PUBLIC,  # 10
    ),
    ACMEDocSpec(
        file="hr_leave_policy.md",
        title="ACME Corporation — Global Employee Leave Policy",
        department=Department.HR,
        access_level=AccessLevel.INTERNAL,  # 20
    ),
    ACMEDocSpec(
        file="travel_per_diem_policy.md",
        title="ACME Corporation — Corporate Travel Expense and Per Diem Guidelines",
        department=Department.HR,
        access_level=AccessLevel.INTERNAL,  # 20
    ),
    ACMEDocSpec(
        file="hr_executive_compensation.md",
        title="ACME Corporation — Executive Compensation and Severance Matrix",
        department=Department.HR,
        access_level=AccessLevel.RESTRICTED,  # 40
    ),
    ACMEDocSpec(
        file="it_security_policy.md",
        title="ACME Corporation — IT Information Security Policy and Controls",
        department=Department.IT,
        access_level=AccessLevel.INTERNAL,  # 20
    ),
    ACMEDocSpec(
        file="it_disaster_recovery.md",
        title="ACME Corporation — Cloud Infrastructure Disaster Recovery Runbook",
        department=Department.IT,
        access_level=AccessLevel.CONFIDENTIAL,  # 30
    ),
    ACMEDocSpec(
        file="customer_support_escalations.md",
        title="ACME Corporation — Tier-3 Customer Support and Incident Escalation Procedures",
        department=Department.SUPPORT,
        access_level=AccessLevel.INTERNAL,  # 20
    ),
    ACMEDocSpec(
        file="adversarial_injection_test.md",
        title="ACME Corporation — Security Audit Report on Legacy Gateway",
        department=Department.IT,
        access_level=AccessLevel.INTERNAL,  # 20
    ),
]

DEMO_USERS = [
    ("admin@acme.corp", UserRole.ADMIN, Department.GENERAL, "AcmeDemo2026!"),
    ("hr.specialist@acme.corp", UserRole.MEMBER, Department.HR, "AcmeDemo2026!"),
    ("sec.analyst@acme.corp", UserRole.MEMBER, Department.IT, "AcmeDemo2026!"),
    ("support.lead@acme.corp", UserRole.MANAGER, Department.SUPPORT, "AcmeDemo2026!"),
]


async def seed() -> None:
    """Run database migration check, tenant seeding, and ACME document ingestion."""
    configure_logging(level="INFO", json_format=False)
    settings = get_settings()
    engine = get_engine(settings)

    print("\n=======================================================")
    print("  ACME Enterprise RAG System — Knowledge Base Seeder   ")
    print("=======================================================\n")
    print(f"Target Database : {settings.DATABASE_URL.split('@')[-1]}")
    print(f"Embedding Engine: {settings.EMBEDDING_PROVIDER}")
    print(f"LLM Engine      : {settings.LLM_PROVIDER}\n")

    # 1. Create tables if not present
    async with engine.begin() as conn:
        print("[1/4] Ensuring PostgreSQL database schema...")
        await conn.run_sync(Base.metadata.create_all)
        print("      Schema ready.")

    factory = get_session_factory(engine)
    password_svc = PasswordService()

    # 2. Seed ACME Tenant
    async with factory() as session:
        tenant_repo = PostgresTenantRepository(session)
        user_repo = PostgresUserRepository(session)

        print("[2/4] Provisioning ACME Enterprise tenant...")
        acme_tenant = await tenant_repo.get_by_slug("acme")
        if not acme_tenant:
            acme_tenant = Tenant(
                name="ACME Enterprise Corporation",
                slug="acme",
            )
            acme_tenant = await tenant_repo.create(acme_tenant)
            print(f"      Created tenant: '{acme_tenant.name}' ({acme_tenant.id})")
        else:
            print(f"      Found existing tenant: '{acme_tenant.name}' ({acme_tenant.id})")

        # 3. Seed Demo Users
        print("[3/4] Provisioning demonstration user accounts...")
        for email, role, dept, raw_pass in DEMO_USERS:
            existing_user = await user_repo.get_by_email(acme_tenant.id, email)
            if not existing_user:
                hashed = password_svc.hash_password(raw_pass)
                user = User(
                    tenant_id=acme_tenant.id,
                    email=email,
                    hashed_password=hashed,
                    role=role,
                    department=dept,
                )
                await user_repo.create(user)
                print(f"      Created: {email:26} [role={role.value:7} dept={dept.value:8}]")
            else:
                print(f"      Existing: {email:25} [role={role.value:7} dept={dept.value:8}]")

        await session.commit()

    # 4. Ingest ACME Knowledge Base Documents
    print("[4/4] Ingesting ACME demonstration documents...")
    dataset_dir = Path(__file__).parent.parent / "examples" / "dataset" / "acme"

    admin_auth = AuthContext(
        tenant_id=acme_tenant.id,
        user_id=acme_tenant.id,
        email="admin@acme.corp",
        role=UserRole.ADMIN,
        department=Department.GENERAL,
        max_clearance=AccessLevel.RESTRICTED,
    )

    async with tenant_scoped_session(tenant_id=acme_tenant.id, settings=settings) as t_session:
        doc_repo = PostgresDocumentRepository(t_session)
        chunk_repo = PostgresChunkRepository(t_session)
        embedding_adapter = get_embedding_provider(settings)
        chunker = RecursiveTokenChunker(
            default_chunk_size=settings.CHUNK_SIZE_TOKENS,
            default_overlap=settings.CHUNK_OVERLAP_TOKENS,
        )
        ingestion_svc = DocumentIngestionService(
            document_repo=doc_repo,
            chunk_repo=chunk_repo,
            parser_factory=ParserRegistry(),
            chunker=chunker,
            embedding_provider=embedding_adapter,
        )

        for doc_spec in ACME_DOCUMENTS:
            doc_path = dataset_dir / doc_spec.file
            if not doc_path.exists():
                print(f"      [SKIP] File not found: {doc_spec.file}")
                continue

            content = doc_path.read_bytes()
            result = await ingestion_svc.ingest_document(
                auth_context=admin_auth,
                title=doc_spec.title,
                content=content,
                filename=doc_spec.file,
                declared_mime="text/markdown",
                department=doc_spec.department,
                access_level=doc_spec.access_level,
            )

            status_label = "DUPLICATE" if result.is_duplicate else f"CHUNKS={result.chunks_created}"
            print(
                f"      Ingested: {doc_spec.title[:45]:45} "
                f"[{doc_spec.department.value:7} clr={doc_spec.access_level.value:2}] "
                f"-> {status_label}"
            )

    await engine.dispose()

    print("\n=======================================================")
    print("  ACME Enterprise Knowledge Base Ready!                ")
    print("=======================================================\n")
    print("You can now test the API using:")
    print("  uvicorn src.main:app --host 0.0.0.0 --port 8000\n")
    print("Demo Credentials (all accounts use password: AcmeDemo2026!):")
    print("  - Admin  : admin@acme.corp         (Full Clearance RESTRICTED 40)")
    print("  - HR     : hr.specialist@acme.corp  (HR Clearance INTERNAL 20)")
    print("  - IT     : sec.analyst@acme.corp    (IT Clearance INTERNAL 20)")
    print("  - Support: support.lead@acme.corp   (Support Clearance CONFIDENTIAL 30)\n")


if __name__ == "__main__":
    asyncio.run(seed())
