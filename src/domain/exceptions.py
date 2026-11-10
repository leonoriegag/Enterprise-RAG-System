"""Domain exceptions for Enterprise RAG System."""


class DomainException(Exception):
    """Base domain exception."""

    def __init__(self, message: str) -> None:
        super().__init__(message)
        self.message = message


class TenantNotFoundError(DomainException):
    """Raised when tenant is not found."""


class UserNotFoundError(DomainException):
    """Raised when user is not found."""


class DocumentNotFoundError(DomainException):
    """Raised when document does not exist."""


class AccessDeniedError(DomainException):
    """Raised when user lacks required permissions."""


class CrossTenantViolationError(DomainException):
    """Raised when an operation attempts to breach tenant boundaries."""


class IngestionError(DomainException):
    """Raised when document parsing or indexing fails."""


class DuplicateDocumentError(DomainException):
    """Raised when an identical document hash already exists in tenant."""


class ProviderUnavailableError(DomainException):
    """Raised when external AI provider fails."""


class InsufficientEvidenceError(DomainException):
    """Raised when retrieved context is insufficient to answer the question."""
