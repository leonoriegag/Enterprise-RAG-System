"""Authentication routes for credential validation and JWT issuance."""

from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, status

from src.application.auth.context import AuthContext
from src.application.auth.service import PasswordService, TokenService
from src.domain.interfaces.repositories import TenantRepository, UserRepository
from src.interfaces.api.dependencies import (
    get_current_auth,
    get_password_service,
    get_tenant_repository,
    get_token_service,
    get_user_repository,
)
from src.interfaces.api.schemas.auth import TokenRequest, TokenResponse, UserProfileResponse
from src.shared.config import Settings, get_settings
from src.shared.logging import get_logger

logger = get_logger(__name__)

router = APIRouter(prefix="/api/v1/auth", tags=["Authentication"])


@router.post(
    "/token",
    response_model=TokenResponse,
    status_code=status.HTTP_200_OK,
    summary="Obtain JWT access token",
    description=(
        "Authenticates tenant user with email and password, returning a signed JWT "
        "with authorization claims."
    ),
)
async def login_for_access_token(
    payload: TokenRequest,
    tenant_repo: Annotated[TenantRepository, Depends(get_tenant_repository)],
    user_repo: Annotated[UserRepository, Depends(get_user_repository)],
    password_service: Annotated[PasswordService, Depends(get_password_service)],
    token_service: Annotated[TokenService, Depends(get_token_service)],
    settings: Annotated[Settings, Depends(get_settings)],
) -> TokenResponse:
    """Validate credentials and issue JWT bearer access token."""
    # 1. Resolve tenant by slug
    tenant = await tenant_repo.get_by_slug(payload.tenant_slug)
    if not tenant or not tenant.is_active():
        logger.warning(
            f"Authentication failed: tenant '{payload.tenant_slug}' not found or inactive"
        )
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid organization or credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 2. Resolve user within tenant
    user = await user_repo.get_by_email(tenant.id, payload.email)
    if not user or not user.is_active:
        logger.warning(f"Authentication failed: user '{payload.email}' not found or inactive")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid organization or credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 3. Verify password
    if not password_service.verify_password(payload.password, user.hashed_password):
        logger.warning(f"Authentication failed: invalid password for user '{payload.email}'")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid organization or credentials",
            headers={"WWW-Authenticate": "Bearer"},
        )

    # 4. Generate signed JWT token
    access_token = token_service.create_access_token(user)
    expires_in_seconds = settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60

    logger.info(f"User '{user.email}' logged in successfully for tenant '{tenant.slug}'")
    return TokenResponse(
        access_token=access_token,
        token_type="bearer",
        expires_in=expires_in_seconds,
    )


@router.get(
    "/me",
    response_model=UserProfileResponse,
    status_code=status.HTTP_200_OK,
    summary="Get current user profile",
    description="Returns caller identity, tenant association, role, department, and clearance.",
)
async def read_current_user_profile(
    auth: Annotated[AuthContext, Depends(get_current_auth)],
) -> UserProfileResponse:
    """Return caller's authorization claims decoded from active JWT token."""
    return UserProfileResponse(
        user_id=auth.user_id,
        tenant_id=auth.tenant_id,
        email=auth.email,
        role=auth.role.value,
        department=auth.department.value,
        max_clearance=auth.max_clearance.value,
    )
