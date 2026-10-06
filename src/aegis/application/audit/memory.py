"""In-process append-only audit log for the sync gateway and CI."""

from __future__ import annotations

from uuid import UUID

from aegis.domain.audit.entity import GENESIS_HASH, AuditEntry


class MemoryAuditRepository:
    """No UPDATE/DELETE. Worker drains rows into Postgres after the graph."""

    def __init__(self) -> None:
        self._entries: list[AuditEntry] = []

    def append_sync(self, entry: AuditEntry) -> AuditEntry:
        self._entries.append(entry)
        return entry

    async def append(self, entry: AuditEntry) -> AuditEntry:
        return self.append_sync(entry)

    async def get(self, audit_id: UUID) -> AuditEntry | None:
        for entry in self._entries:
            if entry.id == audit_id:
                return entry
        return None

    async def list_by_incident(self, incident_id: str) -> list[AuditEntry]:
        return [entry for entry in self._entries if entry.incident_id == incident_id]

    def latest_hash_sync(self) -> str:
        if not self._entries:
            return GENESIS_HASH
        return self._entries[-1].row_hash

    async def latest_hash(self) -> str:
        return self.latest_hash_sync()

    @property
    def entries(self) -> tuple[AuditEntry, ...]:
        return tuple(self._entries)

    def drain(self) -> list[AuditEntry]:
        items = list(self._entries)
        self._entries.clear()
        return items
