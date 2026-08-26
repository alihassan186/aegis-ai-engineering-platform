# ADR-002: Use PostgreSQL as the System of Record

**Status:** Accepted  
**Date:** 2026-08-26  
**Deciders:** Engineering  
**Related:** [System boundaries](../architecture/system-boundaries.md), [NFR-060](../requirements/non-functional-requirements.md)

---

## Context

AEGIS must persist structured data with strong consistency guarantees:

- Incident lifecycle and state transitions
- Evidence items linked to incidents
- RCA reports with version history
- Audit logs (append-only)
- Approval records
- User and role data
- Investigation workflow state

This data is relational, transactional, and subject to integrity constraints. Loss or corruption of incident/audit data is unacceptable.

---

## Problem

Which database technology should serve as the primary system of record for AEGIS operational and audit data?

Requirements:
- ACID transactions for incident state transitions
- Complex queries across incidents, evidence, and audit records
- Schema evolution via migrations
- Append-only audit log support
- JSON support for semi-structured agent outputs
- Managed service option on AWS for production deployment

---

## Decision

Use **PostgreSQL** (Amazon RDS PostgreSQL in production) as the system of record for all structured AEGIS data.

- SQLAlchemy 2.x as the ORM with async support
- Alembic for schema migrations
- Separate tables for audit logs with INSERT-only permissions for the application role
- JSONB columns for semi-structured fields (agent outputs, evidence metadata, RCA details)
- Amazon RDS with automated backups and point-in-time recovery in production

**Redis** will be used separately for caching and ephemeral workflow state — not as a system of record.

**OpenSearch** will be used separately for vector/keyword search (RAG) — not as a system of record.

---

## Alternatives considered

### Alternative 1: Amazon DynamoDB

**Rejected because:**
- Incident/evidence/audit data is inherently relational (incidents have many evidence items, many audit entries)
- Complex queries (e.g., "all incidents for service X in the last 30 days with failed investigations") are awkward in DynamoDB
- No native schema migration tooling equivalent to Alembic
- Audit log append-only pattern requires careful key design to avoid hot partitions
- Learning value: SQL and relational modeling are more transferable skills

### Alternative 2: MongoDB

**Rejected because:**
- Schema flexibility is not a primary requirement — AEGIS data is well-structured
- Weaker consistency guarantees for financial/audit-grade data
- JSONB in PostgreSQL provides sufficient semi-structured flexibility
- Less mature managed option on AWS (DocumentDB has compatibility limitations)

### Alternative 3: SQLite (development) + PostgreSQL (production)

**Considered for development convenience.**

Deferred — use PostgreSQL in both development (Docker) and production to avoid dialect differences. SQLite may be used for unit tests with in-memory database if test speed requires it.

---

## Trade-offs

| Benefit | Cost |
|---|---|
| Strong ACID consistency for incident state | Vertical scaling limits without read replicas |
| Rich query capabilities (joins, aggregations) | Requires connection pooling management |
| Alembic migrations — reproducible schema evolution | RDS cost higher than DynamoDB at very low scale |
| JSONB for flexible agent output storage | JSONB queries less performant than native document store for deep nesting |
| Mature ecosystem (SQLAlchemy, asyncpg, psycopg) | Requires SQL knowledge for complex queries |
| Point-in-time recovery with RDS | Single-region initially (see RISK-009) |

---

## Consequences

### Positive

- Incident state transitions are transactional — no partial updates
- Audit log integrity enforced at database level (INSERT-only role)
- Complex reporting queries (incident metrics, SLO calculations) are straightforward
- Alembic migrations versioned in Git alongside code
- JSONB handles evolving agent output schemas without schema migrations for every change

### Negative

- Must manage connection pooling (SQLAlchemy pool + RDS proxy at scale)
- Read scaling requires read replicas (not needed until v0.8+)
- Local development requires Docker PostgreSQL container

### Schema design principles

1. All tables have `created_at` and `updated_at` timestamps
2. Audit log table: no UPDATE or DELETE grants for application role
3. Soft delete for incidents (never hard delete — audit requirement)
4. Foreign keys enforced at database level
5. JSONB used for: agent outputs, evidence metadata, RCA details — not for core relational data

### Implementation notes (for future reference)

- Use `asyncpg` driver with SQLAlchemy async session
- Connection pool: `pool_size=5`, `max_overflow=10` initially
- RDS instance: `db.t3.micro` for development/staging; `db.t3.medium` for production v1.0
- Enable `pg_stat_statements` for query performance monitoring

---

## Related documents

- [ADR-001: Modular monolith](ADR-001-modular-monolith.md)
- [Non-functional requirements](../requirements/non-functional-requirements.md)
- [Threat model — THR-004](../security/threat-model.md)
