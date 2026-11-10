"""API route controllers."""

from src.interfaces.api.routers.admin import router as admin_router
from src.interfaces.api.routers.auth import router as auth_router
from src.interfaces.api.routers.documents import router as documents_router
from src.interfaces.api.routers.health import router as health_router
from src.interfaces.api.routers.rag import router as rag_router
from src.interfaces.api.routers.retrieval import router as retrieval_router

__all__ = [
    "admin_router",
    "auth_router",
    "documents_router",
    "health_router",
    "rag_router",
    "retrieval_router",
]
