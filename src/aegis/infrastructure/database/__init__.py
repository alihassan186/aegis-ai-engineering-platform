"""PostgreSQL persistence (ADR-002)."""

from aegis.infrastructure.database.base import Base
from aegis.infrastructure.database.session import get_db_session

__all__ = ["Base", "get_db_session"]
