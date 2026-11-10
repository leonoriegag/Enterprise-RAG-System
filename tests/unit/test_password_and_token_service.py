"""Unit tests for password hashing and JWT token service."""

from uuid import uuid4

import pytest

from src.application.auth.service import PasswordService, TokenService
from src.domain.entities.user import User
from src.domain.exceptions import AccessDeniedError
from src.domain.value_objects.department import Department
from src.domain.value_objects.role import UserRole
from src.shared.config import Settings


def test_password_hashing_and_verification() -> None:
    hasher = PasswordService(iterations=10_000)
    raw_pass = "SecureP@ssw0rd2026!"

    hashed = hasher.hash_password(raw_pass)
    assert hashed.startswith("pbkdf2:sha256:10000$")
    assert raw_pass not in hashed

    assert hasher.verify_password(raw_pass, hashed) is True
    assert hasher.verify_password("WrongPassword!", hashed) is False
    assert hasher.verify_password("", hashed) is False


def test_jwt_token_creation_and_decoding() -> None:
    settings = Settings(
        SECRET_KEY="test-secret-key-at-least-32-chars-long!",
        ACCESS_TOKEN_EXPIRE_MINUTES=30,
    )
    token_service = TokenService(settings)

    tenant_id = uuid4()
    user = User(
        tenant_id=tenant_id,
        email="eng@acme.com",
        hashed_password="hash",
        role=UserRole.MANAGER,
        department=Department.ENGINEERING,
    )

    token = token_service.create_access_token(user)
    assert isinstance(token, str)
    assert len(token) > 20

    auth_context = token_service.decode_token(token)
    assert auth_context.tenant_id == tenant_id
    assert auth_context.user_id == user.id
    assert auth_context.email == "eng@acme.com"
    assert auth_context.role == UserRole.MANAGER
    assert auth_context.department == Department.ENGINEERING
    assert auth_context.is_manager is True


def test_tampered_token_rejection() -> None:
    settings = Settings(
        SECRET_KEY="test-secret-key-at-least-32-chars-long!",
    )
    token_service = TokenService(settings)

    with pytest.raises(AccessDeniedError):
        token_service.decode_token("tampered.fake.jwt.token")
