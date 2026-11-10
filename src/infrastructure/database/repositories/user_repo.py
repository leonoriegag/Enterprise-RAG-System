"""SQLAlchemy implementation of UserRepository."""

from uuid import UUID

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from src.domain.entities.user import User
from src.domain.value_objects.department import Department
from src.domain.value_objects.role import UserRole
from src.infrastructure.database.models import UserModel


class PostgresUserRepository:
    """PostgreSQL repository for User entity."""

    def __init__(self, session: AsyncSession) -> None:
        self.session = session

    async def get_by_id(self, user_id: UUID) -> User | None:
        stmt = select(UserModel).where(UserModel.id == user_id)
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def get_by_email(self, tenant_id: UUID, email: str) -> User | None:
        stmt = select(UserModel).where(
            UserModel.tenant_id == tenant_id,
            UserModel.email == email.strip().lower(),
        )
        result = await self.session.execute(stmt)
        model = result.scalar_one_or_none()
        return self._to_entity(model) if model else None

    async def create(self, user: User) -> User:
        model = UserModel(
            id=user.id,
            tenant_id=user.tenant_id,
            email=user.email.strip().lower(),
            hashed_password=user.hashed_password,
            role=user.role.value,
            department=user.department.value,
            is_active=user.is_active,
            created_at=user.created_at,
        )
        self.session.add(model)
        await self.session.flush()
        return user

    async def list_by_tenant(self, tenant_id: UUID) -> list[User]:
        stmt = select(UserModel).where(UserModel.tenant_id == tenant_id).order_by(UserModel.email)
        result = await self.session.execute(stmt)
        models = result.scalars().all()
        return [self._to_entity(m) for m in models]

    def _to_entity(self, model: UserModel) -> User:
        return User(
            id=model.id,
            tenant_id=model.tenant_id,
            email=model.email,
            hashed_password=model.hashed_password,
            role=UserRole(model.role),
            department=Department.from_str(model.department),
            is_active=model.is_active,
            created_at=model.created_at,
        )
