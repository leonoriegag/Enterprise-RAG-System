"""API Pydantic schemas for request validation and response serialization."""

from src.interfaces.api.schemas.auth import (
    TokenRequest,
    TokenResponse,
    UserProfileResponse,
)
from src.interfaces.api.schemas.common import ErrorDetail, ErrorResponse, PaginationParams
from src.interfaces.api.schemas.documents import (
    DocumentDeleteResponse,
    DocumentDetailResponse,
    DocumentListResponse,
    DocumentReindexResponse,
    DocumentUploadResponse,
)
from src.interfaces.api.schemas.health import ComponentStatus, HealthResponse, HealthStatus
from src.interfaces.api.schemas.rag import AskRequest, AskResponse, CitationItem
from src.interfaces.api.schemas.retrieval import SearchRequest, SearchResponse, SearchResultItem
from src.interfaces.api.schemas.tenants import (
    TenantCreateRequest,
    TenantListResponse,
    TenantResponse,
)
from src.interfaces.api.schemas.users import (
    UserCreateRequest,
    UserListResponse,
    UserResponse,
)

__all__ = [
    "AskRequest",
    "AskResponse",
    "CitationItem",
    "ComponentStatus",
    "DocumentDeleteResponse",
    "DocumentDetailResponse",
    "DocumentListResponse",
    "DocumentReindexResponse",
    "DocumentUploadResponse",
    "ErrorDetail",
    "ErrorResponse",
    "HealthResponse",
    "HealthStatus",
    "PaginationParams",
    "SearchRequest",
    "SearchResponse",
    "SearchResultItem",
    "TenantCreateRequest",
    "TenantListResponse",
    "TenantResponse",
    "TokenRequest",
    "TokenResponse",
    "UserCreateRequest",
    "UserListResponse",
    "UserProfileResponse",
    "UserResponse",
]
