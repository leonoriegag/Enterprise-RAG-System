"""Unit tests for configuration settings and structured logging."""

from src.shared.config import Settings
from src.shared.logging import mask_sensitive_str, sanitize_payload


def test_settings_embedding_dimension_selection() -> None:
    mock_settings = Settings(EMBEDDING_PROVIDER="mock", MOCK_EMBEDDING_DIM=384)
    assert mock_settings.embedding_dimension == 384

    openai_settings = Settings(EMBEDDING_PROVIDER="openai", OPENAI_EMBEDDING_DIM=1536)
    assert openai_settings.embedding_dimension == 1536


def test_secret_masking_in_logs() -> None:
    raw_log = (
        "Header contains Bearer eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9 and api_key='sk-123456789'"
    )
    masked = mask_sensitive_str(raw_log)

    assert "eyJhbGci" not in masked
    assert "sk-123456789" not in masked
    assert "[REDACTED]" in masked


def test_sanitize_payload_scrubs_sensitive_keys() -> None:
    payload = {
        "user": "alice",
        "authorization": "Bearer secret-token",
        "password": "plain-password",
        "nested": {
            "api_key": "secret-key-123",
            "normal_field": "visible",
        },
    }

    sanitized = sanitize_payload(payload)
    assert sanitized["user"] == "alice"
    assert sanitized["authorization"] == "[REDACTED]"
    assert sanitized["password"] == "[REDACTED]"
    assert sanitized["nested"]["api_key"] == "[REDACTED]"
    assert sanitized["nested"]["normal_field"] == "visible"
