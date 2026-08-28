"""SQLAlchemy declarative base for ORM models (ADR-002).

ORM classes live in ``aegis.infrastructure.database.models``. Domain entities
stay free of SQLAlchemy (ADR-001).
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    """Shared metadata for all persistence models."""
