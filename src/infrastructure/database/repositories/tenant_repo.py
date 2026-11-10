"""SQLAlchemy implementation of TenantRepository."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.tenant import Tenant
from src.infrastructure.database.models import TenantModel


class PostgresTenantRepository:
    """PostgreSQL repository for Tenant entity."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, tenant_id: UUID) -> Tenant | None:
        stmt = select(TenantModel).where(TenantModel.id == tenant_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_slug(self, slug: str) -> Tenant | None:
        stmt = select(TenantModel).where(TenantModel.slug == slug)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def create(self, tenant: Tenant) -> Tenant:
        model = TenantModel(
            id=tenant.id,
            name=tenant.name,
            slug=tenant.slug,
            status=tenant.status,
            settings=tenant.settings,
            created_at=tenant.created_at,
        )
        self.session.add(model)
        await self.session.flush()
        return tenant

    async def list_active(self) -> list[Tenant]:
        stmt = select(TenantModel).where(TenantModel.status == "active").order_by(TenantModel.name)
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    def _to_entity(self, model: TenantModel) -> Tenant:
        return Tenant(
            id=model.id,
            name=model.name,
            slug=model.slug,
            status=model.status,
            settings=model.settings,
            created_at=model.created_at,
        )
