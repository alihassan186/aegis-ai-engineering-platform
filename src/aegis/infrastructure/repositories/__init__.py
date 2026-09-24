"""Persistence adapters. Application code depends on protocols, not these classes."""

from aegis.infrastructure.repositories.evidence_repository import SqlAlchemyEvidenceRepository
from aegis.infrastructure.repositories.incident_repository import SqlAlchemyIncidentRepository
from aegis.infrastructure.repositories.investigation_repository import (
    SqlAlchemyInvestigationProgressRepository,
)
from aegis.infrastructure.repositories.mappers import to_domain, to_orm
from aegis.infrastructure.repositories.notification_repository import (
    SqlAlchemyNotificationRepository,
)
from aegis.infrastructure.repositories.rca_repository import SqlAlchemyRcaRepository

__all__ = [
    "SqlAlchemyEvidenceRepository",
    "SqlAlchemyIncidentRepository",
    "SqlAlchemyInvestigationProgressRepository",
    "SqlAlchemyNotificationRepository",
    "SqlAlchemyRcaRepository",
    "to_domain",
    "to_orm",
]
