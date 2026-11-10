"""Authentication service for password hashing and JWT token lifecycle."""

import hashlib
import hmac
import os
from datetime import UTC, datetime, timedelta
from typing import Any
from uuid import UUID

import jwt

from src.application.auth.context import AuthContext
from src.domain.entities.user import User
from src.domain.exceptions import AccessDeniedError
from src.domain.value_objects.access_level import AccessLevel
from src.domain.value_objects.department import Department
from src.domain.value_objects.role import UserRole
from src.shared.config import Settings


class PasswordService:
    """Cryptographic password hashing and verification using PBKDF2-HMAC-SHA256."""

    def __init__(self, iterations: int = 100_000) -> None:
        self.iterations = iterations

    def hash_password(self, password: str) -> str:
        """Hash password with a unique 16-byte cryptographic salt."""
        salt = os.urandom(16)
        key = hashlib.pbkdf2_hmac(
            "sha256",
            password.encode("utf-8"),
            salt,
            self.iterations,
        )
        return f"pbkdf2:sha256:{self.iterations}${salt.hex()}${key.hex()}"

    def verify_password(self, plain_password: str, hashed_password: str) -> bool:
        """Verify plain password against stored salt and PBKDF2 hash."""
        try:
            algorithm_part, salt_hex, key_hex = hashed_password.split("$")
            _, _, iterations_str = algorithm_part.split(":")
            iterations = int(iterations_str)
            salt = bytes.fromhex(salt_hex)
            expected_key = bytes.fromhex(key_hex)
            computed_key = hashlib.pbkdf2_hmac(
                "sha256",
                plain_password.encode("utf-8"),
                salt,
                iterations,
            )
            return hmac.compare_digest(computed_key, expected_key)
        except Exception:
            return False


class TokenService:
    """JWT token creation and decoding."""

    def __init__(self, settings: Settings) -> None:
        self.secret_key = settings.SECRET_KEY
        self.algorithm = settings.ALGORITHM
        self.expire_minutes = settings.ACCESS_TOKEN_EXPIRE_MINUTES

    def create_access_token(self, user: User) -> str:
        """Generate signed JWT token containing user identity and authorization claims."""
        now = datetime.now(UTC)
        expires_at = now + timedelta(minutes=self.expire_minutes)

        payload: dict[str, Any] = {
            "sub": str(user.id),
            "tenant_id": str(user.tenant_id),
            "email": user.email,
            "role": user.role.value,
            "department": user.department.value,
            "max_clearance": user.max_access_level.value,
            "iat": int(now.timestamp()),
            "exp": int(expires_at.timestamp()),
        }
        return jwt.encode(payload, self.secret_key, algorithm=self.algorithm)

    def decode_token(self, token: str) -> AuthContext:
        """Decode and validate JWT token into an immutable AuthContext."""
        try:
            payload = jwt.decode(token, self.secret_key, algorithms=[self.algorithm])
            return AuthContext(
                tenant_id=UUID(payload["tenant_id"]),
                user_id=UUID(payload["sub"]),
                email=payload["email"],
                role=UserRole(payload["role"]),
                department=Department.from_str(payload["department"]),
                max_clearance=AccessLevel(payload["max_clearance"]),
            )
        except jwt.ExpiredSignatureError as e:
            raise AccessDeniedError("Access token has expired") from e
        except (jwt.PyJWTError, KeyError, ValueError) as e:
            raise AccessDeniedError("Invalid authentication token") from e
