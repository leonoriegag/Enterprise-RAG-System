"""Authentication and password hashing protocols."""

from typing import Any, Protocol


class PasswordHasher(Protocol):
    """Protocol for cryptographic password hashing."""

    def hash(self, password: str) -> str: ...
    def verify(self, plain_password: str, hashed_password: str) -> bool: ...


class TokenService(Protocol):
    """Protocol for JWT token encoding and decoding."""

    def create_token(self, payload: dict[str, Any], expires_minutes: int = 60) -> str: ...
    def decode_token(self, token: str) -> dict[str, Any]: ...
