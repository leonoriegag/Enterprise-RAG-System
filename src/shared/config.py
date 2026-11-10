"""Application configuration management via Pydantic Settings."""

from functools import lru_cache
from typing import Literal

from pydantic import Field
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Central configuration for Enterprise RAG System."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=True,
        extra="ignore",
    )

    # Application settings
    APP_ENV: Literal["development", "staging", "production", "test"] = "development"
    APP_NAME: str = "Enterprise RAG System"
    DEBUG: bool = False
    LOG_LEVEL: str = "INFO"

    # Security & Authentication
    SECRET_KEY: str = Field(
        default="development-insecure-secret-key-32-chars-minimum-change-in-prod",
        min_length=32,
    )
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60

    # Database Configuration
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/enterprise_rag"
    DB_ECHO: bool = False
    DB_POOL_SIZE: int = 10
    DB_MAX_OVERFLOW: int = 20

    # AI Provider Configuration
    EMBEDDING_PROVIDER: Literal["mock", "openai"] = "mock"
    LLM_PROVIDER: Literal["mock", "openai"] = "mock"

    # Mock Adapter Configuration
    MOCK_EMBEDDING_DIM: int = 384

    # OpenAI Configuration
    OPENAI_API_KEY: str = ""
    OPENAI_BASE_URL: str = "https://api.openai.com/v1"
    OPENAI_MODEL: str = "gpt-4o-mini"
    OPENAI_EMBEDDING_MODEL: str = "text-embedding-3-small"
    OPENAI_EMBEDDING_DIM: int = 1536

    # Ingestion & Chunking
    MAX_UPLOAD_SIZE_MB: int = 25
    CHUNK_SIZE_TOKENS: int = 512
    CHUNK_OVERLAP_TOKENS: int = 64

    # Retrieval & RAG
    DEFAULT_TOP_K: int = 5
    RRF_K_CONSTANT: int = 60
    CONFIDENCE_THRESHOLD: float = 0.65
    MAX_GENERATION_TOKENS: int = 1024
    TEMPERATURE: float = 0.0

    @property
    def embedding_dimension(self) -> int:
        """Return the active embedding dimension depending on the provider."""
        if self.EMBEDDING_PROVIDER == "mock":
            return self.MOCK_EMBEDDING_DIM
        return self.OPENAI_EMBEDDING_DIM


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached application settings singleton."""
    return Settings()
