# AEGIS MCP server (Step 5.5 / FR-065)

MCP is a **transport** into the same tool-use guardrail the investigation
worker already uses. It is not a second policy engine, not a second copy of
the tools, and not Phase 8 remediations.

Cursor / Claude Desktop is **optional**. The process works without an IDE.

## Port and bind

| Process | Bind | Port |
| --- | --- | --- |
| AEGIS API | `127.0.0.1` | **8000** |
| Simulator | `127.0.0.1` | **8001** |
| **MCP** | `127.0.0.1` | **8002** |

Default bind is loopback. Do **not** expose `0.0.0.0` in production. Production
also requires `AEGIS_MCP_TOKEN`. Unauthenticated LAN MCP is denied.

```bash
export AEGIS_MCP_TOKEN=a-long-random-local-token
# optional: AEGIS_MCP_HOST=127.0.0.1 AEGIS_MCP_PORT=8002
uv run python -m mcp
# or: uv run aegis-mcp
# or: uv run uvicorn mcp.server:app --host 127.0.0.1 --port 8002
```

Health: `GET http://127.0.0.1:8002/health`

JSON-RPC: `POST http://127.0.0.1:8002/mcp` with `Authorization: Bearer <token>`.

## Same policy, same gateway

Every MCP call is `ToolGateway.invoke` with a dedicated, untrusted identity:

- `agent_id=mcp_client` (minted here — the client cannot pick `knowledge`)
- classify → agent grants → policy rows (in-process seed, or Postgres when
  `AEGIS_DATABASE_URL` is set and the worker/API have loaded the cache)
- the **same** `src/aegis/tools/` runners as the graph

`mcp_client` is retrieve-only. Listing `fetch_signals` does not grant it.
Invented names such as `delete_rds` are classified destructive and denied.

Local/CI uses `SpecialistPorts.memory()` (fake retrieve / fake code / fake
signals). Simulator HTTP stays on :8001 when the worker injects the real
observability client — MCP does not reimplement that client.

## Point an MCP client at local AEGIS

```json
{
  "mcpServers": {
    "aegis": {
      "url": "http://127.0.0.1:8002/mcp",
      "headers": {
        "Authorization": "Bearer ${AEGIS_MCP_TOKEN}"
      }
    }
  }
}
```

Without an IDE:

```bash
curl -s http://127.0.0.1:8002/health

curl -s http://127.0.0.1:8002/mcp \
  -H "Authorization: Bearer $AEGIS_MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":1,"method":"tools/list","params":{}}'

curl -s http://127.0.0.1:8002/mcp \
  -H "Authorization: Bearer $AEGIS_MCP_TOKEN" \
  -H "Content-Type: application/json" \
  -d '{"jsonrpc":"2.0","id":2,"method":"tools/call","params":{"name":"retrieve_knowledge","arguments":{"query":"latency","service":"payment","scenario":"latency_spike"}}}'
```

A call that invents `delete_rds` returns `allowed: false` / `denied:destructive`.
The runner never executes.

## Auth story

| Environment | Bind | Token |
| --- | --- | --- |
| Local / CI | `127.0.0.1` | Optional on loopback; **set one anyway** |
| Any non-loopback host | refused unless `AEGIS_MCP_TOKEN` is set | Required |
| `AEGIS_ENV=production` | `127.0.0.1` only | Required |

HTTP requests without a matching Bearer token receive **401** when a token is
configured. If no token is configured, only loopback peers are accepted.

## Why MCP *and* a worker?

The worker is the product orchestrator (incident → graph → specialists).
MCP is optional human/IDE access to the **same** governed tools. An IDE
plugin is a confused-deputy risk; it does not get a back door.
