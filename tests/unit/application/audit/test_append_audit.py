"""Allow and deny each mint a redacted audit row (Step 5.6)."""

from __future__ import annotations

from aegis.application.audit.append_audit import AppendAudit
from aegis.application.audit.memory import MemoryAuditRepository
from aegis.application.gateway.invoke_tool import InvokeTool
from aegis.domain.gateway.enums import GatewayVerdict
from aegis.domain.gateway.request import ToolInvokeRequest
from aegis.infrastructure.repositories.audit_repository import SqlAlchemyAuditRepository


def _request(
    tool_name: str,
    *,
    parameters: dict[str, object] | None = None,
) -> ToolInvokeRequest:
    return ToolInvokeRequest(
        agent_id="knowledge",
        tool_name=tool_name,
        parameters=parameters or {"query": "token AKIAIOSFODNN7EXAMPLE"},
        incident_id="11111111-1111-1111-1111-111111111111",
    )


def test_allow_and_deny_each_create_a_row() -> None:
    audit = AppendAudit()
    gateway = InvokeTool(
        tools={"retrieve_knowledge": lambda _p: "runbook excerpt"},
        audit=audit,
    )
    allowed = gateway.invoke(_request("retrieve_knowledge"))
    denied = gateway.invoke(_request("drop_database"))

    rows = audit.log.entries
    assert allowed.audit_id is not None
    assert denied.audit_id is not None
    assert allowed.audit_id != denied.audit_id
    assert len(rows) == 2
    assert rows[0].decision is GatewayVerdict.ALLOW
    assert rows[0].action == "retrieve_knowledge"
    assert rows[1].decision is GatewayVerdict.DENY
    assert rows[1].action == "drop_database"
    assert rows[1].reason == "denied:destructive"
    assert rows[1].prev_hash == rows[0].row_hash


def test_repository_api_has_no_update_or_delete() -> None:
    for cls in (MemoryAuditRepository, SqlAlchemyAuditRepository, AppendAudit):
        assert not hasattr(cls, "update")
        assert not hasattr(cls, "delete")
        assert not hasattr(cls, "save")


def test_redacted_body_is_stored() -> None:
    secret = "AKIAIOSFODNN7EXAMPLE"
    gateway = InvokeTool(tools={"retrieve_knowledge": lambda _p: f"leaked {secret}"})
    decision = gateway.invoke(_request("retrieve_knowledge", parameters={"query": secret}))
    rows = gateway.drain_audit()
    assert len(rows) == 1
    stored = rows[0]
    assert stored.id.hex == decision.audit_id.replace("-", "")
    assert secret not in str(stored.input)
    assert secret not in str(stored.output)
    assert "[REDACTED:aws_access_key]" in str(stored.input)
    assert "[REDACTED:aws_access_key]" in str(stored.output)
