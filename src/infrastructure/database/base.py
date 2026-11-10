"""SQLAlchemy declarative base for PostgreSQL ORM models."""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Base class for all SQLAlchemy database models."""
