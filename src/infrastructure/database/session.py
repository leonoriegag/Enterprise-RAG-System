"""Asynchronous database engine, session factory, and RLS session context."""

from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager
from uuid import UUID

from sqlalchemy import text
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.shared.config import Settings, get_settings

_engine: AsyncEngine | None = None
_session_factory: async_sessionmaker[AsyncSession] | None = None


def get_engine(settings: Settings | None = None) -> AsyncEngine:
    """Return singleton asynchronous database engine."""
    global _engine
    if _engine is None:
        cfg = settings or get_settings()
        _engine = create_async_engine(
            cfg.DATABASE_URL,
            echo=cfg.DB_ECHO,
            pool_size=cfg.DB_POOL_SIZE,
            max_overflow=cfg.DB_MAX_OVERFLOW,
            pool_pre_ping=True,
        )
    return _engine


def get_session_factory(engine: AsyncEngine | None = None) -> async_sessionmaker[AsyncSession]:
    """Return singleton session maker factory."""
    global _session_factory
    if _session_factory is None:
        eng = engine or get_engine()
        _session_factory = async_sessionmaker(
            bind=eng,
            autoflush=False,
            expire_on_commit=False,
            class_=AsyncSession,
        )
    return _session_factory


@asynccontextmanager
async def tenant_scoped_session(
    tenant_id: UUID | None = None,
    settings: Settings | None = None,
) -> AsyncGenerator[AsyncSession, None]:
    """Asynchronous session context manager enforcing PostgreSQL Row-Level Security (RLS)."""
    factory = get_session_factory(get_engine(settings))
    async with factory() as session:
        try:
            if tenant_id is not None:
                # Set PostgreSQL transaction-local setting for RLS policies
                await session.execute(
                    text("SET LOCAL app.current_tenant_id = :tenant_id"),
                    {"tenant_id": str(tenant_id)},
                )
            yield session
            await session.commit()
        except Exception:
            await session.rollback()
            raise
        finally:
            await session.close()
