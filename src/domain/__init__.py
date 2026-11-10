"""Domain layer for Enterprise RAG System.

Contains pure business entities, value objects, exceptions, and protocols.
Must not depend on any outer layers or external frameworks.
"""

from src.domain.entities import (
    Citation,
    Document,
    DocumentChunk,
    GroundedAnswer,
    RetrievedCandidate,
    Tenant,
    User,
)
from src.domain.exceptions import (
    AccessDeniedError,
    CrossTenantViolationError,
    DocumentNotFoundError,
    DomainException,
    DuplicateDocumentError,
    IngestionError,
    InsufficientEvidenceError,
    ProviderUnavailableError,
    TenantNotFoundError,
    UserNotFoundError,
)
from src.domain.value_objects import (
    AccessLevel,
    Department,
    IngestionStatus,
    UserRole,
)

__all__ = [
    "Tenant",
    "User",
    "Document",
    "DocumentChunk",
    "Citation",
    "RetrievedCandidate",
    "GroundedAnswer",
    "UserRole",
    "Department",
    "AccessLevel",
    "IngestionStatus",
    "DomainException",
    "TenantNotFoundError",
    "UserNotFoundError",
    "DocumentNotFoundError",
    "AccessDeniedError",
    "CrossTenantViolationError",
    "IngestionError",
    "DuplicateDocumentError",
    "ProviderUnavailableError",
    "InsufficientEvidenceError",
]
