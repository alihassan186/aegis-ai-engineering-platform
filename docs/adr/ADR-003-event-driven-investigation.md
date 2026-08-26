# ADR-003: Use Event-Driven Processing for Investigation Workflows

**Status:** Accepted  
**Date:** 2026-08-26  
**Deciders:** Engineering  
**Related:** [Incident flow](../architecture/incident-flow.md), [ADR-001](ADR-001-modular-monolith.md)

---

## Context

When an incident is opened, AEGIS must initiate a multi-step investigation workflow:

1. Orchestrator plans evidence collection
2. Multiple agents run sequentially or in parallel
3. Each agent may call external tools (observability APIs, GitHub, RAG)
4. RCA agent synthesizes findings
5. Results are persisted and notifications sent

This workflow is long-running (minutes), involves multiple retries, and must survive process restarts. The API that receives the incident signal must respond quickly without waiting for investigation completion.

---

## Problem

How should investigation workflows be initiated and processed?

Requirements:
- API responds immediately on incident creation (async processing)
- Workflows survive application restarts
- Failed steps are retried without duplicating work
- Multiple investigations can run concurrently
- Failed messages are captured for inspection (dead-letter queue)
- Workflow steps are auditable

---

## Decision

Use **Amazon EventBridge + Amazon SQS** for investigation workflow processing:

```text
Incident API
     │
     ▼
EventBridge (incident.opened.v1)
     │
     ▼
SQS Queue (investigation-workflow)
     │
     ▼
Investigation Worker (ECS task / async consumer)
     │
     ├── success → next event published
     └── failure → retry (3x) → DLQ
```

- **EventBridge** routes domain events to appropriate SQS queues
- **SQS** provides at-least-once delivery, visibility timeout, and DLQ
- **Investigation worker** is an async consumer within the modular monolith (same codebase, separate process/thread initially)
- All event handlers must be **idempotent** (safe to process duplicate messages)
- Event schemas are versioned (`incident.opened.v1`, `evidence.collected.v1`, etc.)

---

## Alternatives considered

### Alternative 1: Synchronous processing in API request

Investigation runs inline when incident is created.

**Rejected because:**
- API response time becomes investigation duration (minutes) — violates NFR-011
- API timeout would kill long-running investigations
- No retry mechanism on failure
- Blocks API worker thread/process during LLM calls

### Alternative 2: Celery + Redis

Use Celery task queue with Redis broker.

**Rejected because:**
- Adds Redis as a required dependency for workflow reliability (Redis is already planned for caching, but not as a message broker)
- Celery operational complexity (workers, beat, monitoring)
- AWS-native SQS integrates with CloudWatch, IAM, and DLQ without additional infrastructure
- Learning objective includes understanding AWS queue semantics directly

### Alternative 3: AWS Step Functions

Use Step Functions to orchestrate investigation steps as a state machine.

**Considered — viable for v0.8+.**

Deferred because:
- Step Functions adds cost per state transition (expensive for agent loops with many steps)
- Local development and testing is harder than in-process async consumers
- LangGraph already provides orchestration logic — Step Functions would duplicate it
- May revisit for remediation workflows (v0.9) where step sequencing and approval gates map naturally to Step Functions

### Alternative 4: PostgreSQL as message queue (SKIP LOCKED)

Use PostgreSQL table as a job queue with `SELECT FOR UPDATE SKIP LOCKED`.

**Rejected because:**
- Couples workflow reliability to database availability
- No native DLQ, visibility timeout, or retry semantics
- Does not scale independently from database
- Useful as a fallback pattern but not primary queue

---

## Trade-offs

| Benefit | Cost |
|---|---|
| API responds immediately | Eventual consistency — investigation starts asynchronously |
| Workflows survive restarts | At-least-once delivery requires idempotent handlers |
| Independent scaling of workers | SQS visibility timeout must be tuned to agent step duration |
| DLQ captures failed investigations for inspection | Duplicate message handling adds implementation complexity |
| AWS-native — IAM, CloudWatch, alarms | Vendor lock-in to AWS SQS semantics |
| Event schema versioning enables safe evolution | Schema migration requires careful versioning discipline |

---

## Consequences

### Positive

- Incident API meets latency SLO (SLO-002) regardless of investigation duration
- Failed agent steps retry automatically without user intervention
- DLQ provides inspectable failure queue for debugging
- Multiple investigations process concurrently via queue consumer scaling
- Event catalog (see incident-flow.md) provides clear contract for all workflow steps

### Negative

- Idempotency must be implemented for every event handler
- Visibility timeout must exceed maximum agent step duration (recommend: 5 minutes initially)
- Duplicate events may cause duplicate evidence collection (acceptable if idempotent)
- Local development requires LocalStack or ElasticMQ for SQS emulation

### Implementation rules

1. Every event handler checks idempotency key (`incident_id` + `event_type` + `step_id`) before processing
2. SQS visibility timeout: 300 seconds (5 minutes) — revisit when agent steps are measured
3. Max receive count: 3 before DLQ
4. EventBridge event bus: dedicated `aegis-events` bus (not default)
5. All events include: `event_id`, `event_type`, `schema_version`, `timestamp`, `correlation_id`
6. Investigation worker logs `correlation_id` on every step for distributed tracing

### Local development

Use LocalStack or ElasticMQ Docker container for local SQS/EventBridge emulation. Document setup in `docs/runbooks/local-development.md` (future).

---

## Related documents

- [Incident flow](../architecture/incident-flow.md)
- [ADR-001: Modular monolith](ADR-001-modular-monolith.md)
- [Functional requirements FR-020](../requirements/functional-requirements.md)
- [SLO-010](../requirements/slos-and-slis.md)
