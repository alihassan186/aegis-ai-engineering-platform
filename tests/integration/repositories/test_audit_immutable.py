"""AUDIT_LOG is append-only for the app role (THR-004)."""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.ext.asyncio import AsyncSession

from aegis.application.audit.append_audit import AppendAudit
from aegis.domain.gateway.enums import GatewayVerdict
from aegis.infrastructure.repositories.audit_repository import SqlAlchemyAuditRepository

_SECRET = "AKIAIOSFODNN7EXAMPLE"
_INCIDENT = "11111111-1111-1111-1111-111111111111"


async def _append(session: AsyncSession) -> object:
    repo = SqlAlchemyAuditRepository(session)
    return await AppendAudit().execute(
        repository=repo,
        actor="knowledge",
        action="retrieve_knowledge",
        incident_id=_INCIDENT,
        decision=GatewayVerdict.ALLOW,
        reason="allowed:read",
        input={"query": f"token {_SECRET}"},
        output={"value": f"runbook {_SECRET}"},
        action_class="read",
    )


async def test_appended_row_is_redacted_and_selectable(db_session: AsyncSession) -> None:
    entry = await _append(db_session)
    loaded = await SqlAlchemyAuditRepository(db_session).get(entry.id)
    assert loaded is not None
    assert loaded.decision is GatewayVerdict.ALLOW
    assert _SECRET not in str(loaded.input)
    assert _SECRET not in str(loaded.output)
    assert "[REDACTED:aws_access_key]" in str(loaded.input)
    listed = await SqlAlchemyAuditRepository(db_session).list_by_incident(_INCIDENT)
    assert [row.id for row in listed] == [entry.id]


async def test_update_as_app_role_is_rejected(db_session: AsyncSession) -> None:
    entry = await _append(db_session)
    with pytest.raises(DBAPIError, match="append-only"):
        async with db_session.begin_nested():
            await db_session.execute(
                text("UPDATE audit_log SET actor = 'evil' WHERE id = :id"),
                {"id": entry.id},
            )
            await db_session.flush()
    loaded = await SqlAlchemyAuditRepository(db_session).get(entry.id)
    assert loaded is not None
    assert loaded.actor == "knowledge"


async def test_delete_as_app_role_is_rejected(db_session: AsyncSession) -> None:
    entry = await _append(db_session)
    with pytest.raises(DBAPIError, match="append-only"):
        async with db_session.begin_nested():
            await db_session.execute(
                text("DELETE FROM audit_log WHERE id = :id"),
                {"id": entry.id},
            )
            await db_session.flush()
    loaded = await SqlAlchemyAuditRepository(db_session).get(entry.id)
    assert loaded is not None
