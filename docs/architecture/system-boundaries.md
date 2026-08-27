# System Boundaries

**Document owner:**  Ali Hassan  
**Status:** Draft  
**Last updated:** 2026-08-26

Defines what is inside and outside AEGIS, module boundaries within the system, and interface contracts between components.

---

## 1. System boundary

### Inside AEGIS


| Component                | Responsibility                                                      |
| ------------------------ | ------------------------------------------------------------------- |
| **HTTP API**             | External interface for users and webhook ingestion                  |
| **Domain layer**         | Incident, evidence, RCA, remediation, approval entities and rules   |
| **Application layer**    | Use cases, investigation orchestration, workflow state machines     |
| **Infrastructure layer** | PostgreSQL, Redis, Bedrock, OpenSearch, SQS, external API clients   |
| **Agent runtime**        | Specialized agents and orchestration (LangGraph)                    |
| **RAG pipeline**         | Ingestion, chunking, embedding, indexing, retrieval                 |
| **Tool gateway**         | Policy enforcement, authorization, audit logging for all tool calls |
| **Evaluation pipeline**  | Golden dataset runs, metric collection, regression detection        |
| **Production simulator** | Synthetic multi-service environment for dev and test                |




### Outside AEGIS


| System                         | Relationship                                                                 |
| ------------------------------ | ---------------------------------------------------------------------------- |
| Observability platforms        | Data source — AEGIS reads, does not store primary telemetry                  |
| Alerting / paging              | Signal source — AEGIS receives, does not manage on-call schedules            |
| GitHub / CI/CD                 | Integration target — AEGIS reads code/deploy history; controlled writes only |
| Target production applications | Subject of investigation — AEGIS does not host application workloads         |
| Identity provider (future)     | Authentication source — AEGIS validates tokens, does not manage users        |


---



## 2. Layered architecture

```text
┌─────────────────────────────────────────────────────────────────┐
│                        Presentation                             │
│              FastAPI routes · Webhooks · OpenAPI                │
├─────────────────────────────────────────────────────────────────┤
│                        Application                              │
│     Use cases · Investigation orchestrator · Approval flows     │
├─────────────────────────────────────────────────────────────────┤
│                          Domain                                 │
│   Incident · Evidence · RCA · Remediation · Policy · Audit      │
├─────────────────────────────────────────────────────────────────┤
│                       Infrastructure                            │
│  PostgreSQL · Redis · Bedrock · OpenSearch · SQS · Ext APIs     │
└─────────────────────────────────────────────────────────────────┘
                              ▲
                              │ tool calls
                    ┌─────────┴─────────┐
                    │   Tool Gateway    │
                    │  Policy · Auth ·  │
                    │  Audit · Rate lim │
                    └─────────┬─────────┘
                              │
              ┌───────────────┼───────────────┐
              ▼               ▼               ▼
         Observability     GitHub          Production
           APIs             API           (via approval)
```



### Dependency rule

Dependencies point **inward only**:

- Domain layer has no dependencies on infrastructure or frameworks
- Application layer depends on domain abstractions, not concrete infrastructure
- Infrastructure implements interfaces defined by domain/application layers

---



## 3. Module boundaries (repository mapping)


| Repository path             | Layer          | Boundary                                                        |
| --------------------------- | -------------- | --------------------------------------------------------------- |
| `src/aegis/domain/`         | Domain         | Pure business logic, entities, value objects, domain services   |
| `src/aegis/application/`    | Application    | Use cases, orchestration, workflow handlers                     |
| `src/aegis/infrastructure/` | Infrastructure | DB repos, Bedrock client, OpenSearch client, SQS publishers     |
| `src/aegis/config/`         | Cross-cutting  | Settings, environment configuration                             |
| `src/aegis/shared/`         | Cross-cutting  | Shared types, exceptions, utilities                             |
| `src/aegis/core/`           | Cross-cutting  | Base classes, interfaces, protocols                             |
| `agents/`                   | Application    | Agent implementations (one package per agent role)              |
| `mcp/`                      | Infrastructure | MCP server definitions and tool gateway                         |
| `tools/`                    | Infrastructure | Concrete tool implementations behind gateway                    |
| `services/`                 | Application    | Domain-specific service modules (incident, investigation, etc.) |
| `apps/api/`                 | Presentation   | API service entry point (wraps `aegis.main`)                    |
| `apps/simulator/`           | Infrastructure | Production environment simulator                                |
| `evaluation/`               | Application    | Benchmark runners, datasets, metrics                            |


---



## 4. Interface contracts



### API boundary

- RESTful HTTP/JSON
- OpenAPI 3.x specification auto-generated from FastAPI
- Authentication: Bearer token (JWT initially)
- All responses include `request_id` for correlation
- Error format: `{ "error": { "code": "...", "message": "...", "request_id": "..." } }`



### Agent boundary

- Agents communicate via orchestrator (LangGraph state machine)
- Agents do not call each other directly
- Agents invoke tools only through the tool gateway interface
- Agent outputs are structured (Pydantic models), not free-form text for critical decisions



### Tool gateway boundary

```text
Input:  { agent_id, tool_name, parameters, incident_id, action_class }
Output: { success, result | error, audit_id }
Policy: { allowed: bool, reason: string, requires_approval: bool }
```



### Event boundary

- Investigation events published to SQS via EventBridge
- Event schema versioned (e.g., `incident.opened.v1`)
- Consumers must be idempotent (at-least-once delivery)
- Dead-letter queue for failed processing after max retries



### RAG boundary

- Ingestion pipeline produces indexed chunks with metadata
- Retrieval accepts: query, filters (service, doc_type, date), top_k
- Retrieval returns: ranked chunks with source citations
- Retrieved content is passed to LLM as **data**, never as **instructions**

---



## 5. Data ownership


| Data                         | Owner                  | Store                      | Retention                       |
| ---------------------------- | ---------------------- | -------------------------- | ------------------------------- |
| Incidents                    | AEGIS                  | PostgreSQL                 | Configurable (default 1 year)   |
| Evidence items               | AEGIS                  | PostgreSQL                 | Linked to incident lifecycle    |
| RCA reports                  | AEGIS                  | PostgreSQL                 | Linked to incident lifecycle    |
| Audit logs                   | AEGIS                  | PostgreSQL (append-only)   | Minimum 90 days                 |
| Document embeddings          | AEGIS                  | OpenSearch                 | Refreshed on re-index           |
| Investigation workflow state | AEGIS                  | PostgreSQL + Redis (cache) | Duration of investigation       |
| Raw logs/metrics/traces      | Observability platform | External                   | Not stored permanently in AEGIS |
| Source code                  | GitHub                 | External                   | Not stored permanently in AEGIS |


---



## 6. Security boundaries


| Boundary                | Control                                        |
| ----------------------- | ---------------------------------------------- |
| User → API              | Authentication + RBAC                          |
| API → Domain            | Input validation, authorization check          |
| Agent → Tool gateway    | Agent identity + action classification         |
| Tool gateway → External | Scoped credentials, rate limits, audit         |
| RAG → LLM               | Content treated as untrusted; secrets redacted |
| LLM → Agent output      | Schema validation, confidence thresholds       |


---



## 7. Explicit non-boundaries

The following are intentionally **not** part of AEGIS core boundaries:

- **User management** — delegated to identity provider or simple JWT (v0.2)
- **Primary observability storage** — AEGIS queries, does not replace CloudWatch/Datadog
- **Source code hosting** — AEGIS searches GitHub, does not host repos
- **On-call scheduling** — AEGIS receives alerts, does not manage schedules
- **Network infrastructure** — VPC, subnets, security groups managed by CDK, not application code

---



## Related documents

- [System context](context.md)
- [Incident flow](incident-flow.md)
- [Threat model](../security/threat-model.md)
- [Functional requirements](../requirements/functional-requirements.md)

