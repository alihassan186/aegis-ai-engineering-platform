"""MCP-compatible door into the same tool gateway (FR-065).

Transport only. Every call is ``InvokeTool`` with ``agent_id=mcp_client``.
Default bind is loopback :8002. This is not a second tool implementation
and not Phase 8 remediations.
"""

from __future__ import annotations

import os
import secrets
from collections.abc import Mapping
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse

from aegis.application.gateway.bind_ports import invoke_tool_for_ports
from aegis.application.gateway.invoke_tool import InvokeTool
from aegis.application.gateway.registry import READ_TOOL_NAMES
from aegis.application.investigation.collect import SpecialistPorts
from aegis.domain.auth.agent_identity import AgentIdentity
from aegis.domain.gateway.decision import GatewayDecision
from aegis.domain.gateway.request import ToolInvokeRequest

DEFAULT_HOST = "127.0.0.1"
DEFAULT_PORT = 8002
LOOPBACK_HOSTS = frozenset({"127.0.0.1", "localhost", "::1"})
MCP_INCIDENT_ID = "mcp"
PROTOCOL_VERSION = "2024-11-05"

_TOOL_META: dict[str, dict[str, Any]] = {
    "retrieve_knowledge": {
        "description": "Retrieve allowlisted runbooks and incident reports (read).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "query": {"type": "string"},
                "service": {"type": "string"},
                "scenario": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    "fetch_signals": {
        "description": "Fetch simulator/observability signal summaries (read).",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service": {"type": "string"},
                "scenario": {"type": "string"},
                "limit": {"type": "integer"},
            },
            "additionalProperties": False,
        },
    },
    "search_code": {
        "description": "Search the fake/catalog code index (read). Does not walk src/.",
        "inputSchema": {
            "type": "object",
            "properties": {
                "service": {"type": "string"},
                "scenario": {"type": "string"},
            },
            "additionalProperties": False,
        },
    },
    "list_deploys": {
        "description": "List recent deploy versions from the code port (read).",
        "inputSchema": {
            "type": "object",
            "properties": {"service": {"type": "string"}},
            "additionalProperties": False,
        },
    },
}


class McpSettings:
    """Process settings. Secrets stay in the environment (NFR-032)."""

    def __init__(
        self,
        *,
        host: str = DEFAULT_HOST,
        port: int = DEFAULT_PORT,
        token: str = "",
        environment: str = "development",
    ) -> None:
        self.host = host
        self.port = port
        self.token = token
        self.environment = environment

    @classmethod
    def from_env(cls) -> McpSettings:
        raw_port = os.getenv("AEGIS_MCP_PORT", "").strip()
        try:
            port = int(raw_port) if raw_port else DEFAULT_PORT
        except ValueError:
            port = DEFAULT_PORT
        if port <= 0:
            port = DEFAULT_PORT
        return cls(
            host=os.getenv("AEGIS_MCP_HOST", DEFAULT_HOST).strip() or DEFAULT_HOST,
            port=port,
            token=os.getenv("AEGIS_MCP_TOKEN", "").strip(),
            environment=os.getenv("AEGIS_ENV", "development").strip().lower() or "development",
        )


def validate_bind(settings: McpSettings) -> None:
    """Fail closed: no unauthenticated LAN MCP; production stays loopback + token."""
    loopback = settings.host in LOOPBACK_HOSTS
    if not loopback and not settings.token:
        raise ValueError("MCP must not bind a non-loopback address without AEGIS_MCP_TOKEN.")
    if settings.environment == "production" and not settings.token:
        raise ValueError("AEGIS_MCP_TOKEN is required when AEGIS_ENV=production.")
    if settings.environment == "production" and not loopback:
        raise ValueError("MCP must bind 127.0.0.1 in production. Do not use 0.0.0.0.")


class McpServer:
    """Lists registry tools and forwards every call through the gateway."""

    def __init__(self, gateway: InvokeTool, *, token: str = "") -> None:
        self._gateway = gateway.bind(AgentIdentity.MCP_CLIENT)
        self.token = token

    def list_tools(self) -> list[dict[str, Any]]:
        listed: list[dict[str, Any]] = []
        for name in sorted(READ_TOOL_NAMES):
            meta = _TOOL_META.get(
                name,
                {
                    "description": name,
                    "inputSchema": {"type": "object", "additionalProperties": False},
                },
            )
            listed.append(
                {
                    "name": name,
                    "description": meta["description"],
                    "inputSchema": meta["inputSchema"],
                }
            )
        return listed

    def call_tool(
        self,
        name: str,
        arguments: Mapping[str, Any] | None = None,
        *,
        incident_id: str = MCP_INCIDENT_ID,
    ) -> GatewayDecision:
        params = _sanitize_arguments(arguments)
        return self._gateway.invoke(
            ToolInvokeRequest(
                agent_id=AgentIdentity.MCP_CLIENT,
                tool_name=name,
                parameters=params,
                incident_id=incident_id or MCP_INCIDENT_ID,
            )
        )

    def authorize(self, presented: str, *, peer_host: str = "") -> None:
        if self.token:
            if not presented or not secrets.compare_digest(presented, self.token):
                raise PermissionError("denied:mcp_unauthorized")
            return
        if peer_host and peer_host not in LOOPBACK_HOSTS:
            raise PermissionError("denied:mcp_loopback_only")


def build_mcp_server(
    *,
    ports: SpecialistPorts | None = None,
    token: str | None = None,
    gateway: InvokeTool | None = None,
) -> McpServer:
    """Compose registry runners + gateway. Defaults keep CI on fakes."""
    bound_ports = ports or SpecialistPorts.memory()
    invoke = gateway or invoke_tool_for_ports(bound_ports)
    resolved = token if token is not None else McpSettings.from_env().token
    return McpServer(invoke, token=resolved)


def create_app(server: McpServer | None = None) -> FastAPI:
    mcp_server = server or build_mcp_server()
    app = FastAPI(title="AEGIS MCP", docs_url=None, redoc_url=None)
    app.state.mcp = mcp_server

    @app.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok", "service": "aegis-mcp"}

    @app.post("/mcp")
    async def mcp_rpc(request: Request) -> JSONResponse:
        _require_http_auth(request, mcp_server)
        try:
            body = await request.json()
        except Exception as exc:
            raise HTTPException(status_code=400, detail="invalid JSON-RPC body") from exc
        return JSONResponse(_dispatch_rpc(mcp_server, body if isinstance(body, dict) else {}))

    return app


app = create_app()


def main() -> None:
    import uvicorn

    settings = McpSettings.from_env()
    validate_bind(settings)
    uvicorn.run(
        "mcp.server:app",
        host=settings.host,
        port=settings.port,
        reload=False,
    )


def _sanitize_arguments(arguments: Mapping[str, Any] | None) -> dict[str, Any]:
    params = dict(arguments or {})
    params.pop("agent_id", None)
    params.pop("action_class", None)
    return params


def _require_http_auth(request: Request, server: McpServer) -> None:
    presented = _bearer_token(request)
    peer = request.client.host if request.client is not None else ""
    try:
        server.authorize(presented, peer_host=peer)
    except PermissionError as exc:
        raise HTTPException(status_code=401, detail=str(exc)) from exc


def _bearer_token(request: Request) -> str:
    header = request.headers.get("authorization", "")
    prefix = "bearer "
    if header.lower().startswith(prefix):
        return header[len(prefix) :].strip()
    return header.strip()


def _dispatch_rpc(server: McpServer, body: Mapping[str, Any]) -> dict[str, Any]:
    rpc_id = body.get("id")
    method = str(body.get("method") or "")
    params = body.get("params") if isinstance(body.get("params"), Mapping) else {}
    if method == "initialize":
        return _rpc_result(
            rpc_id,
            {
                "protocolVersion": PROTOCOL_VERSION,
                "capabilities": {"tools": {}},
                "serverInfo": {"name": "aegis-mcp", "version": "0.6.0"},
            },
        )
    if method == "tools/list":
        return _rpc_result(rpc_id, {"tools": server.list_tools()})
    if method == "tools/call":
        name = str(params.get("name") or "")
        arguments = params.get("arguments") if isinstance(params.get("arguments"), Mapping) else {}
        incident_id = str(params.get("incident_id") or MCP_INCIDENT_ID)
        if not name:
            return _rpc_error(rpc_id, -32602, "tool name is required")
        decision = server.call_tool(name, arguments, incident_id=incident_id)
        return _rpc_result(rpc_id, _decision_payload(decision))
    return _rpc_error(rpc_id, -32601, f"unknown method '{method}'")


def _decision_payload(decision: GatewayDecision) -> dict[str, Any]:
    text = decision.reason if not decision.allowed else "allowed:read"
    return {
        "allowed": decision.allowed,
        "reason": decision.reason,
        "agent_id": decision.agent_id,
        "action_class": None if decision.action_class is None else decision.action_class.value,
        "result": decision.result,
        "error": decision.error,
        "audit_id": decision.audit_id,
        "policy_version": decision.policy_version,
        "untrusted": decision.untrusted,
        "isError": not decision.allowed,
        "content": [
            {
                "type": "text",
                "text": text if not decision.allowed else _result_text(decision),
            }
        ],
    }


def _result_text(decision: GatewayDecision) -> str:
    """Prefer the 5.9 envelope text: redacted, directive lines dropped, still untrusted data."""
    envelope = decision.envelope
    if envelope is not None:
        return str(envelope.get("text") or "")
    result = decision.result
    if result is None:
        return decision.reason
    return str(result)


def _rpc_result(rpc_id: Any, result: Mapping[str, Any]) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rpc_id, "result": result}


def _rpc_error(rpc_id: Any, code: int, message: str) -> dict[str, Any]:
    return {"jsonrpc": "2.0", "id": rpc_id, "error": {"code": code, "message": message}}
