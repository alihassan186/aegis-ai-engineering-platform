"""AEGIS — Autonomous Engineering & Incident Response System."""

from aegis.shared.exceptions import DomainError, NotFoundError, ValidationError

__all__ = ["DomainError", "NotFoundError", "ValidationError", "__version__"]
__version__ = "0.1.0"
