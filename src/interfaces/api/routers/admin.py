"""Tenant and user administration endpoints restricted to administrative roles."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.application.auth.context import AuthContext
from src.application.auth.service import PasswordService
from src.domain.entities.tenant import Tenant
from src.domain.entities.user import User
from src.domain.interfaces.repositories import TenantRepository, UserRepository
from src.domain.value_objects.department import Department
from src.domain.value_objects.role import UserRole
from src.interfaces.api.dependencies import (
    get_password_service,
    get_tenant_repository,
    get_user_repository,
    require_admin,
)
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
from src.shared.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/admin", tags=["Administration"])


@router.post(
    "/tenants",
    response_model=TenantResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Provision new tenant organization",
    description="Registers an isolated enterprise tenant boundary. Requires ADMIN privileges.",
)
async def create_tenant(
    payload: TenantCreateRequest,
    _admin: Annotated[AuthContext, Depends(require_admin)],
    tenant_repo: Annotated[TenantRepository, Depends(get_tenant_repository)],
) -> TenantResponse:
    """Create a new enterprise tenant organization."""
    existing = await tenant_repo.get_by_slug(payload.slug)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"Tenant with slug '{payload.slug}' already exists",
        )

    tenant = Tenant(
        name=payload.name,
        slug=payload.slug,
    )
    saved = await tenant_repo.create(tenant)

    logger.info(f"Provisioned tenant '{saved.slug}' ({saved.id}) by admin {_admin.email}")
    return TenantResponse(
        id=saved.id,
        name=saved.name,
        slug=saved.slug,
        is_active=saved.is_active(),
        created_at=saved.created_at,
    )


@router.get(
    "/tenants",
    response_model=TenantListResponse,
    status_code=status.HTTP_200_OK,
    summary="List active tenants",
    description="Lists all active tenant organizations. Requires ADMIN privileges.",
)
async def list_tenants(
    _admin: Annotated[AuthContext, Depends(require_admin)],
    tenant_repo: Annotated[TenantRepository, Depends(get_tenant_repository)],
) -> TenantListResponse:
    """List all registered active tenants."""
    tenants = await tenant_repo.list_active()
    items = [
        TenantResponse(
            id=t.id,
            name=t.name,
            slug=t.slug,
            is_active=t.is_active(),
            created_at=t.created_at,
        )
        for t in tenants
    ]
    return TenantListResponse(total=len(items), items=items)


@router.post(
    "/users",
    response_model=UserResponse,
    status_code=status.HTTP_201_CREATED,
    summary="Create tenant user",
    description=(
        "Provisions a user account within caller's tenant with assigned role and department. "
        "Requires ADMIN privileges."
    ),
)
async def create_user(
    payload: UserCreateRequest,
    admin: Annotated[AuthContext, Depends(require_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    password_service: Annotated[PasswordService, Depends(get_password_service)],
) -> UserResponse:
    """Create a user account in caller's tenant."""
    existing = await user_repo.get_by_email(admin.tenant_id, payload.email)
    if existing:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=f"User '{payload.email}' already exists in this tenant",
        )

    role_val = UserRole(payload.role)
    dept_val = Department.from_str(payload.department)
    hashed = password_service.hash_password(payload.password)

    user = User(
        tenant_id=admin.tenant_id,
        email=payload.email,
        hashed_password=hashed,
        role=role_val,
        department=dept_val,
    )
    saved = await user_repo.create(user)

    logger.info(
        f"Created user '{saved.email}' (role={saved.role.value}, dept={saved.department.value}) "
        f"in tenant {admin.tenant_id}"
    )

    return UserResponse(
        id=saved.id,
        tenant_id=saved.tenant_id,
        email=saved.email,
        role=saved.role.value,
        department=saved.department.value,
        max_clearance=saved.max_access_level.value,
        is_active=saved.is_active,
        created_at=saved.created_at,
    )


@router.get(
    "/users",
    response_model=UserListResponse,
    status_code=status.HTTP_200_OK,
    summary="List users in tenant",
    description="Lists all users belonging to caller's tenant. Requires ADMIN privileges.",
)
async def list_users(
    admin: Annotated[AuthContext, Depends(require_admin)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
) -> UserListResponse:
    """List all user accounts in caller's tenant."""
    users = await user_repo.list_by_tenant(admin.tenant_id)
    items = [
        UserResponse(
            id=u.id,
            tenant_id=u.tenant_id,
            email=u.email,
            role=u.role.value,
            department=u.department.value,
            max_clearance=u.max_access_level.value,
            is_active=u.is_active,
            created_at=u.created_at,
        )
        for u in users
    ]
    return UserListResponse(total=len(items), items=items)
