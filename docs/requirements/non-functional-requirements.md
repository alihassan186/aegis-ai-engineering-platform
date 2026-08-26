# Non-Functional Requirements

**Document owner:** Engineering  
**Status:** Draft  
**Last updated:** 2026-08-26

Non-functional requirements define **how** the system must behave — quality attributes that constrain design and implementation.

---

## 1. Reliability

| ID | Requirement | Target |
|---|---|---|
| NFR-001 | API availability during normal operations | ≥ 99.5% monthly uptime |
| NFR-002 | Investigation workflows shall survive transient downstream failures (Bedrock timeout, OpenSearch unavailable) with retry and graceful degradation | No data loss; escalation on persistent failure |
| NFR-003 | Message processing shall be at-least-once with idempotent handlers | Duplicate events do not corrupt state |
| NFR-004 | Failed investigation steps shall be retried with exponential backoff | Max 3 retries before escalation |
| NFR-005 | Database connections shall use connection pooling with health checks | Pool exhaustion triggers alert |
| NFR-006 | The system shall support graceful shutdown without losing in-flight investigations | Drain period ≥ 30 seconds |

---

## 2. Performance

| ID | Requirement | Target |
|---|---|---|
| NFR-010 | API health check response time | p99 < 100ms |
| NFR-011 | Incident creation API response time | p99 < 500ms |
| NFR-012 | Investigation initiation (enqueue to first agent step) | p99 < 5 seconds |
| NFR-013 | End-to-end investigation (signal to initial RCA) | p95 < 10 minutes (complex incidents may exceed) |
| NFR-014 | RAG retrieval latency | p95 < 2 seconds |
| NFR-015 | Concurrent investigations supported | ≥ 10 simultaneous (v1.0) |
| NFR-016 | API throughput | ≥ 100 requests/second (v1.0) |

---

## 3. Scalability

| ID | Requirement | Target |
|---|---|---|
| NFR-020 | API layer shall be horizontally scalable (stateless) | Scale to 3+ instances without code change |
| NFR-021 | Investigation workers shall scale independently via queue consumer count | Add consumers without downtime |
| NFR-022 | OpenSearch index shall support ≥ 100,000 document chunks | v1.0 |
| NFR-023 | PostgreSQL shall support ≥ 10,000 incidents with full evidence history | v1.0 |
| NFR-024 | Architecture shall not require redesign at 10x incident volume | Validated at v0.8 |

---

## 4. Security

| ID | Requirement | Target |
|---|---|---|
| NFR-030 | All API endpoints shall require authentication (except health check) | v0.2 |
| NFR-031 | All data in transit shall be encrypted (TLS 1.2+) | Always |
| NFR-032 | Secrets shall never be stored in source code or logs | Always |
| NFR-033 | Agent service accounts shall operate under least-privilege IAM policies | v0.6 |
| NFR-034 | LLMs shall never receive raw AWS credentials or production database connection strings | Always |
| NFR-035 | All agent tool invocations shall be logged with actor, action, inputs, and outcome | v0.6 |
| NFR-036 | Prompt inputs shall be sanitized; retrieved documents shall be treated as untrusted | v0.4 |
| NFR-037 | High-risk and destructive actions shall require human approval | v0.9 |
| NFR-038 | Audit logs shall be append-only and tamper-evident | v0.7 |

---

## 5. Observability

| ID | Requirement | Target |
|---|---|---|
| NFR-040 | All services shall emit structured JSON logs | v0.2 |
| NFR-041 | All API requests shall include a correlation/request ID | v0.2 |
| NFR-042 | Agent execution steps shall be traceable via distributed tracing | v0.8 |
| NFR-043 | Key metrics shall be exported: request latency, error rate, queue depth, investigation duration, Bedrock token usage | v0.8 |
| NFR-044 | Alerts shall fire on: API error rate > 1%, queue depth > threshold, investigation failure rate > 10% | v0.8 |
| NFR-045 | Bedrock invocation latency and token consumption shall be tracked per investigation | v0.5 |

---

## 6. Maintainability

| ID | Requirement | Target |
|---|---|---|
| NFR-050 | Code shall follow a layered architecture with clear module boundaries | v0.2 |
| NFR-051 | All public API endpoints shall have contract tests | v0.2 |
| NFR-052 | Architectural decisions shall be recorded as ADRs | v0.1 |
| NFR-053 | Code shall pass lint (ruff), format, and type check (mypy) in CI | v0.2 |
| NFR-054 | Test coverage for domain logic shall be ≥ 80% | v0.5 |
| NFR-055 | Dependencies shall be pinned via `uv.lock` | v0.1 |

---

## 7. Data management

| ID | Requirement | Target |
|---|---|---|
| NFR-060 | Incident and evidence data shall be persisted in PostgreSQL | v0.2 |
| NFR-061 | Database schema changes shall be managed via Alembic migrations | v0.2 |
| NFR-062 | Investigation data retention shall be configurable (default: 1 year) | v0.7 |
| NFR-063 | Audit logs shall be retained separately from operational data | v0.6 |
| NFR-064 | Data at rest shall be encrypted (RDS encryption, S3 SSE) | v0.7 |
| NFR-065 | Backups shall be automated with point-in-time recovery capability | v0.7 |

---

## 8. Cost

| ID | Requirement | Target |
|---|---|---|
| NFR-070 | Bedrock token usage shall be tracked and attributed per investigation | v0.5 |
| NFR-071 | Infrastructure costs shall be estimatable per investigation | v0.8 |
| NFR-072 | Model selection shall support routing to cheaper models for low-complexity tasks | P2 · v1.0 |
| NFR-073 | RAG retrieval shall use caching for repeated queries within an investigation | P1 · v0.4 |

---

## 9. Usability

| ID | Requirement | Target |
|---|---|---|
| NFR-080 | API shall follow REST conventions with consistent error response format | v0.2 |
| NFR-081 | OpenAPI documentation shall be auto-generated and accessible at `/docs` | v0.2 |
| NFR-082 | Investigation reports shall be readable by engineers without AI expertise | v0.5 |
| NFR-083 | Error messages shall be actionable (include error code, message, correlation ID) | v0.2 |

---

## 10. Compliance & audit

| ID | Requirement | Target |
|---|---|---|
| NFR-090 | All agent decisions and tool calls shall be auditable with timestamp and actor | v0.6 |
| NFR-091 | Human approval decisions shall be recorded with approver identity and timestamp | v0.9 |
| NFR-092 | Data access by agents shall be logged and reviewable | v0.6 |

---

## Related documents

- [Functional requirements](functional-requirements.md)
- [SLOs and SLIs](slos-and-slis.md)
- [Threat model](../security/threat-model.md)
- [Risk register](risk-register.md)
