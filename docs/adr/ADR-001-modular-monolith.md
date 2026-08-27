# ADR-001: Adopt a Modular Monolith as the Initial Architecture

**Status:** Accepted  
**Date:** 2026-08-26  
**Deciders:** Engineering  
**Related:** [System boundaries](../architecture/system-boundaries.md)

---

## Context

AEGIS is a greenfield platform that will grow to include incident management, multi-agent orchestration, RAG, a tool gateway, evaluation pipelines, and AWS infrastructure. We need an initial architectural shape that supports rapid learning and iteration without premature complexity.

The team is a solo developer building incrementally across backend, AI, and cloud domains. Operational overhead must remain manageable through v0.5.

---

## Problem

How should we structure the AEGIS codebase and runtime to:

- Support clear domain boundaries from the start
- Allow incremental feature delivery across multiple capability areas
- Avoid operational complexity that distracts from core learning objectives
- Enable future extraction into services if scale demands it

---

## Decision

Adopt a **modular monolith** as the initial architecture:

- Single deployable unit (FastAPI application on ECS/Fargate)
- Internal modules organized by domain layer (domain, application, infrastructure)
- Separate repository directories for agents, tools, services, and evaluation — but deployed together initially
- Event-driven processing for investigation workflows (see ADR-003) within the same runtime
- Extract to separate services only when a specific module has independent scaling, deployment, or team ownership requirements

---

## Alternatives considered

### Alternative 1: Microservices from day one

Separate services for incident API, agent runtime, RAG pipeline, and tool gateway from the start.

**Rejected because:**
- High operational overhead (service discovery, inter-service auth, distributed tracing setup) before any feature is validated
- Premature boundary decisions — we don't yet know which modules need independent scaling
- Solo developer cannot effectively operate 4+ services in early phases
- Network latency between services adds complexity to agent orchestration

### Alternative 2: Single flat codebase (no layers)

All code in one package without domain/application/infrastructure separation.

**Rejected because:**
- Business logic becomes coupled to FastAPI, SQLAlchemy, and Bedrock directly
- Testing domain logic requires mocking infrastructure everywhere
- Future extraction becomes a large refactor rather than a module boundary change
- Does not teach production-grade layering patterns

### Alternative 3: Serverless-first (Lambda + Step Functions)

Each workflow step as a Lambda function orchestrated by Step Functions.

**Rejected because:**
- Cold start latency is problematic for agent orchestration with multiple sequential LLM calls
- Local development and debugging is significantly harder
- Long-running investigations (minutes) are awkward in Lambda
- Cost model is less predictable for sustained agent workloads

---

## Trade-offs

| Benefit | Cost |
|---|---|
| Simple deployment and debugging | Cannot scale individual modules independently initially |
| Clear module boundaries enable future extraction | Requires discipline to maintain boundary rules |
| Single process — no network calls between modules | All modules share the same failure domain |
| Fast local development with `uv run` | Monolith memory/CPU limits apply to all modules |
| Lower AWS cost in early phases | May require refactor when extraction is needed |

---

## Consequences

### Positive

- Faster iteration in v0.1–v0.5 without infrastructure overhead
- Domain layer can be tested in isolation from day one
- Repository structure (`src/aegis/domain/`, `application/`, `infrastructure/`) enforces boundaries in code
- ADR-gated path to service extraction when justified

### Negative

- Must actively enforce module boundary rules (no direct infrastructure imports in domain)
- Investigation worker and API share resources — a runaway agent could impact API latency
- Future extraction requires explicit ADR and migration plan

### Boundary enforcement rules

1. `domain/` imports nothing from `infrastructure/`, `application/`, or FastAPI
2. `application/` imports from `domain/` only (via interfaces)
3. `infrastructure/` implements interfaces defined in `domain/` or `application/`
4. Agents in `agents/` depend on `application/` use cases, not infrastructure directly
5. Any violation requires explicit ADR justification

### Review trigger

Revisit this decision when:
- Investigation worker CPU/memory consistently exceeds 70% of task allocation
- A module needs independent deployment cadence
- Team grows beyond one developer with separate ownership areas

---

## Related documents

- [System boundaries](../architecture/system-boundaries.md)
- [ADR-003: Event-driven investigation](ADR-003-event-driven-investigation.md)
