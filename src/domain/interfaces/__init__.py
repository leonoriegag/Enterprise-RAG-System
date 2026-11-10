"""Domain protocols and interfaces."""

from src.domain.interfaces.auth import PasswordHasher, TokenService
from src.domain.interfaces.chunker import Chunker, RawChunk
from src.domain.interfaces.embeddings import EmbeddingProvider
from src.domain.interfaces.llm import GenerationResult, LLMProvider
from src.domain.interfaces.parsers import DocumentParser, ParsedDocument, ParsedSection
from src.domain.interfaces.repositories import (
    ChunkRepository,
    DocumentRepository,
    TenantRepository,
    UserRepository,
)
from src.domain.interfaces.retrieval import HybridRetriever, Reranker, RetrievalFilter

__all__ = [
    "TenantRepository",
    "UserRepository",
    "DocumentRepository",
    "ChunkRepository",
    "EmbeddingProvider",
    "LLMProvider",
    "GenerationResult",
    "HybridRetriever",
    "Reranker",
    "RetrievalFilter",
    "DocumentParser",
    "ParsedDocument",
    "ParsedSection",
    "Chunker",
    "RawChunk",
    "PasswordHasher",
    "TokenService",
]
