"""Learning demo: the Phase 5 guardrail allowing, denying and auditing. No Docker.

Run:
    AEGIS_SKIP_DOTENV=1 uv run python scripts/learning/guardrail_demo.py

Read the code top to bottom, then change the CALLS table and run it again.
Every call goes through ``InvokeTool.invoke`` (the one gate). The agent identity
is bound by the caller (``gateway.bind(...)``), not taken from parameters.
"""

from __future__ import annotations

# Import order matters: ``collect`` first avoids a known circular import
# (gateway.bind_ports <-> investigation.collect). See the handbook, section 8.
from aegis.application.investigation.collect import SpecialistPorts
from aegis.application.audit.append_audit import AppendAudit
from aegis.application.gateway.invoke_tool import InvokeTool
from aegis.application.gateway.rate_limit import RateLimiter, ToolRateLimits
from aegis.application.gateway.registry import runners_for_ports
from aegis.domain.audit.entity import GENESIS_HASH
from aegis.domain.auth.agent_identity import AgentIdentity
from aegis.domain.gateway.decision import GatewayDecision
from aegis.domain.gateway.request import ToolInvokeRequest

INCIDENT_ID = "11111111-1111-1111-1111-111111111111"


def build_gateway(*, deny_all: bool = False) -> InvokeTool:
    ports = SpecialistPorts.memory()
    return InvokeTool(
        tools=runners_for_ports(
            observability=ports.observability,
            code_search=ports.code_search,
            retrieve=ports.retrieve,
        ),
        audit=AppendAudit(),
        rate_limiter=RateLimiter(
            limits=ToolRateLimits(
                window_seconds=60.0,
                per_tool_incident=100,
                per_agent=100,
                fail_closed=False,
            )
        ),
        deny_all=lambda: deny_all,
    )


def call(
    gateway: InvokeTool,
    agent: str,
    tool: str,
    params: dict[str, object] | None = None,
    *,
    bind: bool = True,
) -> GatewayDecision:
    """Present one tool call. ``bind`` closes the identity over the gateway."""
    runner = gateway.bind(agent) if bind else gateway
    return runner.invoke(
        ToolInvokeRequest(
            agent_id=agent,
            tool_name=tool,
            parameters=params or {},
            incident_id=INCIDENT_ID,
        )
    )


def show(label: str, agent: str, tool: str, decision: GatewayDecision, note: str = "") -> None:
    print(
        f"{agent:<10} {tool:<19} allowed={decision.allowed!s:<6} "
        f"reason={decision.reason:<26} policy={decision.policy_version}"
        + (f"   ({note})" if note else "")
    )


def main() -> None:
    gateway = build_gateway()

    print("== 1. Decisions ==")
    show("", "knowledge", "retrieve_knowledge",
         call(gateway, "knowledge", "retrieve_knowledge", {"query": "db pool", "service": "payment"}))
    show("", "knowledge", "search_code",
         call(gateway, "knowledge", "search_code", {"service": "payment"}))
    show("", "code", "search_code",
         call(gateway, "code", "search_code", {"service": "../etc/passwd"}), "path traversal")
    show("", "code", "search_code",
         call(gateway, "code", "search_code", {"service": "payment", "url": "http://169.254.169.254"}),
         'extra field "url"')
    show("", "knowledge", "drop_database",
         call(gateway, "knowledge", "drop_database", {}))
    show("", "knowledge", "restart_payment",
         call(gateway, "knowledge", "restart_payment", {}))
    # An invented identity cannot be bound (ValidationError by design), so use the
    # unbound gateway to show the deny.
    show("", "root", "retrieve_knowledge",
         call(gateway, "root", "retrieve_knowledge", {"query": "x"}, bind=False))

    killed = build_gateway(deny_all=True)
    show("", "knowledge", "retrieve_knowledge",
         call(killed, "knowledge", "retrieve_knowledge", {"query": "x"}), "kill switch ON")

    print("\n== 2. Audit rows (every call above is one row) ==")
    for name, gw in (("normal gateway", gateway), ("kill-switch gateway", killed)):
        print(f"-- {name}")
        previous = GENESIS_HASH
        for entry in gw.drain_audit():
            linked = "chain OK" if entry.prev_hash == previous else "CHAIN BROKEN"
            print(
                f"{entry.actor:<10} {entry.action:<19} {entry.decision.value:<6} "
                f"{entry.reason:<26} deny_all={entry.deny_all!s:<5} "
                f"hash={entry.row_hash[:10]} prev={entry.prev_hash[:10]} {linked}"
            )
            previous = entry.row_hash

    print("\n== 3. Envelope on an allowed result (data, not instructions) ==")
    gateway2 = build_gateway()
    decision = call(gateway2, "knowledge", "retrieve_knowledge", {"query": "db pool"})
    print({k: v for k, v in (decision.envelope or {}).items() if k != "text"})
    print("text:", (decision.envelope or {}).get("text", "")[:100], "...")


if __name__ == "__main__":
    main()
