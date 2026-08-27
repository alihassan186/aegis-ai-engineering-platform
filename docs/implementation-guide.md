# AEGIS Implementation Guide

**Document owner:** Engineering  
**Status:** Active  
**Last updated:** 2026-08-26

This is the **master step-by-step guide** for turning AEGIS documentation into working code. Every implementation step links back to the requirement, architecture decision, or design document that justifies it.

> **Rule:** Do not skip ahead. Complete each step, run tests, and check the **Done checklist** before moving to the next step.

---

## Table of contents

1. [How to use this guide](#1-how-to-use-this-guide)
2. [Documentation map](#2-documentation-map)
3. [Current codebase state](#3-current-codebase-state)
4. [Implementation principles](#4-implementation-principles)
5. [Release roadmap overview](#5-release-roadmap-overview)
6. [Phase 0 — Complete v0.1 foundation](#phase-0--complete-v01-foundation)
7. [Phase 1 — v0.2 Core backend](#phase-1--v02-core-backend) ← **START CODING HERE**
8. [Phase 2 — v0.3 Production simulator](#phase-2--v03-production-simulator)
9. [Phase 3 — v0.4 RAG platform](#phase-3--v04-rag-platform)
10. [Phase 4 — v0.5 Multi-agent investigation](#phase-4--v05-multi-agent-investigation)
11. [Phase 5 — v0.6 Tool gateway & MCP](#phase-5--v06-tool-gateway--mcp)
12. [Phase 6 — v0.7 AWS deployment](#phase-6--v07-aws-deployment)
13. [Phase 7 — v0.8 Observability & evaluation](#phase-7--v08-observability--evaluation)
14. [Phase 8 — v0.9 Controlled remediation](#phase-8--v09-controlled-remediation)
15. [Traceability quick reference](#15-traceability-quick-reference)
16. [Per-step template](#16-per-step-template)

---

## 1. How to use this guide

### Your workflow for every step

```text
READ  → Why this step exists (documentation links below)
PLAN  → Which files you will create or change
BUILD → Smallest working slice only
TEST  → Unit → integration → lint → type check
VERIFY → Run commands in "Verification" section
MARK  → Check off Done checklist
NEXT  → Only then proceed to next step
```

### What each step contains

| Field | Purpose |
|---|---|
| **Goal** | One sentence — what works when you're done |
| **Why** | Business and engineering reason |
| **Documentation** | Exact docs that define this step |
| **Implements** | FR/NFR/ADR/THR IDs |
| **Files to create/modify** | Concrete paths in the repo |
| **What to build** | Detailed implementation description |
| **Best practices** | Patterns to follow |
| **Do NOT** | Scope boundaries — avoid jumping ahead |
| **Tests** | What to test |
| **Verification** | Commands to run |
| **Done checklist** | Gate before next step |

---

## 2. Documentation map

Use this table to know **which document answers which question** while coding.

| Question | Document |
|---|---|
| What should the product do? | [Product vision](product/product-vision.md) |
| What must the system implement? | [Functional requirements](requirements/functional-requirements.md) |
| How well must it perform/behave? | [Non-functional requirements](requirements/non-functional-requirements.md) |
| What are the SLO targets? | [SLOs and SLIs](requirements/slos-and-slis.md) |
| What can go wrong? | [Risk register](requirements/risk-register.md) |
| How do components fit together? | [Platform overview (diagrams)](architecture/platform-overview.md) |
| What are the trust boundaries? | [System boundaries](architecture/system-boundaries.md) |
| What is the incident lifecycle? | [Incident flow](architecture/incident-flow.md) |
| What are the security threats? | [Threat model](security/threat-model.md) |
| Why modular monolith? | [ADR-001](adr/ADR-001-modular-monolith.md) |
| Why PostgreSQL? | [ADR-002](adr/ADR-002-postgresql.md) |
| Why event-driven workflows? | [ADR-003](adr/ADR-003-event-driven-investigation.md) |
| Why Bedrock? | [ADR-004](adr/ADR-004-aws-bedrock.md) |

**Primary coding checklist:** [Functional requirements](requirements/functional-requirements.md) filtered by target version.

**Primary architecture reference while coding:** [Platform overview §3–§7](architecture/platform-overview.md).

---

## 3. Current codebase state

| Component | Status | Location |
|---|---|---|
| FastAPI app + `/health` | Implemented | `src/aegis/main.py` |
| Settings | Implemented | `src/aegis/config/settings.py` |
| Domain layer | Empty (`.gitkeep`) | `src/aegis/domain/` |
| Application layer | Empty | `src/aegis/application/` |
| Infrastructure layer | Empty | `src/aegis/infrastructure/` |
| PostgreSQL | Not implemented | — |
| Authentication | Not implemented | — |
| Incident API | Not implemented | — |
| Agents, RAG, AWS | Not implemented | — |

**You are here:** End of v0.1 → Start [Phase 1 (v0.2)](#phase-1--v02-core-backend).

---

## 4. Implementation principles

These come from [Product vision §8](product/product-vision.md) and [ADR-001 boundary rules](adr/ADR-001-modular-monolith.md):

1. **Dependencies point inward** — `domain` has zero infrastructure imports.
2. **One problem per step** — no "while I'm here" refactors.
3. **Test domain logic without database** — pure unit tests for business rules.
4. **Test API with integration tests** — real Postgres in Docker for v0.2+.
5. **Every write endpoint gets auth** — except `/health` ([NFR-030](requirements/non-functional-requirements.md)).
6. **Structured errors** — `{ error: { code, message, request_id } }` ([System boundaries §4](architecture/system-boundaries.md)).
7. **Conventional commits** — `feat:`, `fix:`, `test:` per README Git workflow.
8. **No secrets in code** — use `.env` and [Threat model §10](security/threat-model.md).

### Layer responsibilities (memorize this)

```text
domain/          → WHAT the business rules are (entities, enums, validation)
application/     → HOW use cases orchestrate domain (create incident, transition state)
infrastructure/  → WHERE data lives (SQLAlchemy, repos, external clients)
main.py + routes → HTTP interface (thin — delegates to application layer)
```

---

## 5. Release roadmap overview

| Phase | Version | Focus | Start after |
|---|---|---|---|
| [Phase 0](#phase-0--complete-v01-foundation) | v0.1 | Foundation | — |
| [Phase 1](#phase-1--v02-core-backend) | v0.2 | Incident model, Postgres, auth, API | Phase 0 |
| [Phase 2](#phase-2--v03-production-simulator) | v0.3 | Synthetic failures for testing | Phase 1 |
| [Phase 3](#phase-3--v04-rag-platform) | v0.4 | Knowledge ingestion & retrieval | Phase 2 |
| [Phase 4](#phase-4--v05-multi-agent-investigation) | v0.5 | Agents, evidence, RCA | Phase 3 |
| [Phase 5](#phase-5--v06-tool-gateway--mcp) | v0.6 | Policy, tools, audit | Phase 4 |
| [Phase 6](#phase-6--v07-aws-deployment) | v0.7 | AWS CDK, ECS, RDS | Phase 5 |
| [Phase 7](#phase-7--v08-observability--evaluation) | v0.8 | Metrics, benchmarks | Phase 6 |
| [Phase 8](#phase-8--v09-controlled-remediation) | v0.9 | Approval, remediation | Phase 7 |

---

## Phase 0 — Complete v0.1 foundation

> **Status:** Mostly complete. Run verification below. Skip to Phase 1 if all checks pass.

### Step 0.1 — Verify bootstrap

| | |
|---|---|
| **Goal** | Confirm dev environment works |
| **Documentation** | [README § Getting started](../README.md) |
| **Implements** | FR-112, NFR-055 |

**Verification:**

```bash
uv sync --group dev
uv run pytest
uv run ruff check .
uv run mypy src tests
uv run uvicorn aegis.main:app --reload
curl http://127.0.0.1:8000/health
```

**Done checklist:**
- [ ] All tests pass
- [ ] Lint and mypy pass
- [ ] `/health` returns `{"status":"ok"}`

---

## Phase 1 — v0.2 Core backend

**Release goal:** Engineers can create, list, filter, and manage incidents via a secured REST API backed by PostgreSQL.

**Architecture reference:** [Platform overview §3, §5, §6](architecture/platform-overview.md)

---

### Step 1.1 — Create layered package structure

| | |
|---|---|
| **Goal** | Empty layer directories with clear import boundaries |
| **Why** | [ADR-001](adr/ADR-001-modular-monolith.md) requires domain/application/infrastructure separation from day one so business logic never couples to FastAPI or SQLAlchemy |
| **Documentation** | [ADR-001 § Boundary rules](adr/ADR-001-modular-monolith.md) · [System boundaries §3](architecture/system-boundaries.md) · [Platform overview §4](architecture/platform-overview.md) |
| **Implements** | NFR-050 |

**Files to create:**

```text
src/aegis/domain/__init__.py
src/aegis/application/__init__.py
src/aegis/infrastructure/__init__.py
src/aegis/shared/__init__.py
src/aegis/shared/exceptions.py          # DomainError, NotFoundError, ValidationError
src/aegis/core/__init__.py
src/aegis/core/protocols.py             # Repository interfaces (Protocols)
```

**What to build:**
- Package `__init__.py` files (can be empty)
- Base exception hierarchy in `shared/exceptions.py`
- Empty `Protocol` classes for repositories you'll implement later (e.g. `IncidentRepository`)

**Best practices:**
- No imports from `infrastructure` in `domain/`
- Use `typing.Protocol` for repository interfaces ([ADR-001](adr/ADR-001-modular-monolith.md))

**Do NOT:**
- Add SQLAlchemy, FastAPI routes, or agent code
- Implement business logic yet

**Tests:**
- `tests/unit/test_package_imports.py` — verify layers import without circular dependencies

**Verification:**

```bash
uv run pytest tests/unit/test_package_imports.py
uv run mypy src
```

**Done checklist:**
- [ ] All layer directories exist with `__init__.py`
- [ ] Base exceptions defined
- [ ] No circular imports
- [ ] mypy passes

---

### Step 1.2 — Extend configuration for database

| | |
|---|---|
| **Goal** | Settings load `DATABASE_URL` from environment |
| **Why** | [ADR-002](adr/ADR-002-postgresql.md) — PostgreSQL is the system of record; configuration must be environment-aware for local/staging/production |
| **Documentation** | [ADR-002 § Implementation notes](adr/ADR-002-postgresql.md) · [NFR-060](requirements/non-functional-requirements.md) · [`.env.example`](../config/.env.example) |
| **Implements** | NFR-060, NFR-032 |

**Files to modify:**

```text
src/aegis/config/settings.py
config/.env.example
.env.example                            # add DATABASE_URL if missing
```

**What to build:**
- Add `database_url: str` to `Settings`
- Load from `AEGIS_DATABASE_URL` env var
- Fail fast on startup in non-test environments if URL is missing (optional for Step 1.2, required by Step 1.4)

**Best practices:**
- Never hardcode credentials ([Threat model THR-013](security/threat-model.md))
- Use `postgresql+asyncpg://` driver prefix ([ADR-002](adr/ADR-002-postgresql.md))

**Do NOT:**
- Connect to database yet

**Tests:**
- `tests/unit/test_settings.py` — settings load from env vars

**Verification:**

```bash
uv run pytest tests/unit/test_settings.py
```

**Done checklist:**
- [ ] `DATABASE_URL` documented in `.env.example`
- [ ] Settings dataclass includes database URL
- [ ] Unit tests pass

---

### Step 1.3 — Add PostgreSQL via Docker Compose

| | |
|---|---|
| **Goal** | Local PostgreSQL running with one command |
| **Why** | [ADR-002](adr/ADR-002-postgresql.md) — use same DB locally and in production; Docker avoids "works on my machine" |
| **Documentation** | [ADR-002 § Consequences](adr/ADR-002-postgresql.md) · [Platform overview §12](architecture/platform-overview.md) |
| **Implements** | NFR-060 |

**Files to create:**

```text
docker/docker-compose.yml               # postgres service
docker/.env.example                     # POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
```

**What to build:**
- PostgreSQL 16 container
- Named volume for data persistence
- Port `5432` exposed to host
- Health check on postgres service

**Best practices:**
- Default credentials in `.env.example` only — not production values
- Add `docker/` path to README local dev section (optional doc update)

**Do NOT:**
- Add Redis, OpenSearch, or AWS services yet

**Verification:**

```bash
docker compose -f docker/docker-compose.yml up -d
docker compose -f docker/docker-compose.yml ps   # postgres healthy
```

**Done checklist:**
- [ ] Postgres container starts and is healthy
- [ ] Can connect with `psql` or GUI tool

---

### Step 1.4 — Add SQLAlchemy, Alembic, and database session

| | |
|---|---|
| **Goal** | Application can open async DB sessions and run migrations |
| **Why** | [ADR-002](adr/ADR-002-postgresql.md) mandates SQLAlchemy 2.x async + Alembic for schema evolution |
| **Documentation** | [ADR-002](adr/ADR-002-postgresql.md) · [NFR-061](requirements/non-functional-requirements.md) · [System boundaries §5](architecture/system-boundaries.md) |
| **Implements** | NFR-005, NFR-061 |

**Files to create/modify:**

```text
pyproject.toml                          # add sqlalchemy[asyncio], asyncpg, alembic
src/aegis/infrastructure/database/session.py
src/aegis/infrastructure/database/base.py
alembic.ini
alembic/env.py
alembic/versions/                       # first migration (empty or extensions)
src/aegis/main.py                       # lifespan: connect/disconnect pool
```

**What to build:**
- Async SQLAlchemy engine with connection pool (`pool_size=5`, `max_overflow=10` per ADR-002)
- `async_sessionmaker` factory
- FastAPI lifespan context manager for engine startup/shutdown
- Alembic configured for async migrations
- Dependency injection: `get_db_session()` for route handlers

**Best practices:**
- One session per request — close in finally block
- Use `DeclarativeBase` for ORM models in `infrastructure/database/models/`

**Do NOT:**
- Create incident tables yet (Step 1.6)

**Tests:**
- `tests/integration/test_database_connection.py` — session opens and runs `SELECT 1`

**Verification:**

```bash
uv sync
uv run alembic upgrade head
uv run pytest tests/integration/test_database_connection.py
```

**Done checklist:**
- [ ] Dependencies added to `pyproject.toml` and `uv.lock`
- [ ] Alembic runs successfully
- [ ] Integration test connects to Postgres

---

### Step 1.5 — Implement Incident domain model

| | |
|---|---|
| **Goal** | Pure Python incident entity with state machine rules — no DB, no API |
| **Why** | Domain-first design ([ADR-001](adr/ADR-001-modular-monolith.md)) — business rules tested without infrastructure |
| **Documentation** | [FR-002, FR-003, FR-004, FR-005](requirements/functional-requirements.md) · [Incident flow §1](architecture/incident-flow.md) · [Platform overview §6 ER diagram](architecture/platform-overview.md) |
| **Implements** | FR-002, FR-003, FR-004, FR-005 |

**Files to create:**

```text
src/aegis/domain/incidents/__init__.py
src/aegis/domain/incidents/enums.py         # IncidentState, Severity
src/aegis/domain/incidents/entity.py       # Incident dataclass or class
src/aegis/domain/incidents/transitions.py  # valid state transition rules
src/aegis/domain/incidents/exceptions.py   # InvalidTransitionError
```

**What to build:**

**Incident entity fields:**
- `id: UUID`
- `title: str`
- `description: str | None`
- `state: IncidentState`
- `severity: Severity`
- `affected_service: str`
- `owner_id: UUID | None`
- `created_at: datetime`
- `updated_at: datetime`
- `state_history: list[StateTransition]` (for FR-004)

**States (FR-003):**
```text
open → investigating → identified → remediating → resolved → closed
```

**State transition rules:**
- Define allowed transitions in `transitions.py`
- `transition_to(new_state)` method raises `InvalidTransitionError` on illegal moves
- Record timestamp on each transition (FR-004)

**Best practices:**
- Domain module imports only stdlib + other domain modules
- Use immutable value objects where possible
- 100% unit test coverage on transition logic

**Do NOT:**
- Import SQLAlchemy or FastAPI
- Implement API endpoints

**Tests:**

```text
tests/unit/domain/incidents/test_transitions.py
  - open → investigating: allowed
  - open → resolved: rejected
  - all valid paths from incident-flow.md
  - state_history records timestamp
```

**Verification:**

```bash
uv run pytest tests/unit/domain/ -v
uv run mypy src/aegis/domain
```

**Done checklist:**
- [ ] Incident entity with all FR-005 fields
- [ ] All 6 states defined
- [ ] Transition rules match [incident-flow.md](architecture/incident-flow.md)
- [ ] Unit tests cover valid and invalid transitions
- [ ] No infrastructure imports in domain/

---

### Step 1.6 — PostgreSQL schema and repository

| | |
|---|---|
| **Goal** | Incidents persist to PostgreSQL and load back as domain entities |
| **Why** | [ADR-002](adr/ADR-002-postgresql.md) — system of record; repository pattern keeps domain pure |
| **Documentation** | [ADR-002 § Schema principles](adr/ADR-002-postgresql.md) · [Platform overview §6](architecture/platform-overview.md) · [System boundaries §5](architecture/system-boundaries.md) |
| **Implements** | FR-002, FR-004, NFR-060, NFR-061 |

**Files to create:**

```text
src/aegis/infrastructure/database/models/incident.py    # SQLAlchemy ORM model
src/aegis/infrastructure/database/models/state_history.py
src/aegis/infrastructure/repositories/incident_repository.py
src/aegis/infrastructure/repositories/mappers.py        # ORM ↔ domain entity
alembic/versions/xxxx_create_incidents_table.py
```

**Database schema (`incidents` table):**
- `id` UUID PK
- `title`, `description`, `state`, `severity`, `affected_service`
- `owner_id` UUID nullable FK (users table later — nullable for now)
- `created_at`, `updated_at` timestamps
- Soft delete: `deleted_at` nullable ([ADR-002](adr/ADR-002-postgresql.md))

**Database schema (`incident_state_history` table):**
- `id`, `incident_id` FK, `from_state`, `to_state`, `transitioned_at`

**Repository interface** (in `core/protocols.py`):
```python
class IncidentRepository(Protocol):
    async def create(self, incident: Incident) -> Incident: ...
    async def get_by_id(self, id: UUID) -> Incident | None: ...
    async def list(self, filters: IncidentFilters) -> list[Incident]: ...
    async def save(self, incident: Incident) -> Incident: ...
```

**Best practices:**
- Mapper functions: `to_domain(orm)` / `to_orm(domain)` — never leak ORM into application layer
- Use transactions for create + initial state history insert

**Do NOT:**
- Put query logic in FastAPI routes

**Tests:**
- `tests/integration/repositories/test_incident_repository.py`

**Verification:**

```bash
uv run alembic upgrade head
uv run pytest tests/integration/repositories/ -v
```

**Done checklist:**
- [ ] Migration creates tables with indexes on `state`, `affected_service`, `created_at`
- [ ] Repository CRUD works
- [ ] State history persisted on transitions
- [ ] Integration tests pass against Docker Postgres

---

### Step 1.7 — Application use cases

| | |
|---|---|
| **Goal** | Business operations callable without HTTP — create, get, list, transition |
| **Why** | [ADR-001](adr/ADR-001-modular-monolith.md) — application layer orchestrates domain + repositories; routes stay thin |
| **Documentation** | [System boundaries §2](architecture/system-boundaries.md) · [FR-001–009](requirements/functional-requirements.md) |
| **Implements** | FR-001, FR-002, FR-004, FR-006, FR-009 |

**Files to create:**

```text
src/aegis/application/incidents/__init__.py
src/aegis/application/incidents/create_incident.py
src/aegis/application/incidents/get_incident.py
src/aegis/application/incidents/list_incidents.py
src/aegis/application/incidents/transition_incident.py
src/aegis/application/incidents/dto.py              # request/response DTOs
```

**Use cases:**

| Use case | Input | Output | FR |
|---|---|---|---|
| `CreateIncident` | title, severity, service, description | Incident (state=open) | FR-001, FR-006 |
| `GetIncident` | incident_id | Incident | FR-002 |
| `ListIncidents` | filters: state, severity, service, owner, date | list[Incident] | FR-009 |
| `TransitionIncident` | incident_id, new_state | Incident | FR-003, FR-004 |

**Best practices:**
- Use cases receive repository via constructor (dependency injection)
- Raise domain exceptions; application layer does not know about HTTP

**Tests:**
- `tests/unit/application/incidents/` — mock repository, test use case logic

**Verification:**

```bash
uv run pytest tests/unit/application/ -v
```

**Done checklist:**
- [ ] All four use cases implemented
- [ ] Create sets initial state `open` with timestamp
- [ ] List supports all FR-009 filters
- [ ] Transition delegates to domain state machine

---

### Step 1.8 — REST API routes

| | |
|---|---|
| **Goal** | HTTP API for incident operations with OpenAPI docs |
| **Why** | [FR-110, FR-111](requirements/functional-requirements.md) — REST API is the primary interface; OpenAPI enables contract tests |
| **Documentation** | [System boundaries §4 API boundary](architecture/system-boundaries.md) · [Platform overview §2](architecture/platform-overview.md) · [NFR-080, NFR-081](requirements/non-functional-requirements.md) |
| **Implements** | FR-001, FR-006, FR-009, FR-110, FR-111 |

**Files to create:**

```text
src/aegis/api/__init__.py
src/aegis/api/router.py
src/aegis/api/incidents/router.py
src/aegis/api/incidents/schemas.py          # Pydantic request/response models
src/aegis/api/dependencies.py               # get_db, get_repositories
src/aegis/api/errors.py                     # exception handlers
src/aegis/main.py                           # include router
```

**Endpoints:**

| Method | Path | Use case | FR |
|---|---|---|---|
| `POST` | `/api/v1/incidents` | CreateIncident | FR-001, FR-006 |
| `GET` | `/api/v1/incidents` | ListIncidents | FR-009 |
| `GET` | `/api/v1/incidents/{id}` | GetIncident | FR-002 |
| `PATCH` | `/api/v1/incidents/{id}/state` | TransitionIncident | FR-003 |

**Response format:**
- Success: appropriate HTTP status + JSON body
- Error: `{ "error": { "code": "...", "message": "...", "request_id": "..." } }` ([System boundaries](architecture/system-boundaries.md))
- All responses include `request_id` ([NFR-041](requirements/non-functional-requirements.md))

**Best practices:**
- API versioning prefix `/api/v1/`
- Pydantic schemas separate from domain entities
- HTTP 201 for create, 404 for not found, 422 for validation, 409 for invalid transition

**Do NOT:**
- Add authentication yet (Step 1.9) — optional: implement routes without auth first, then protect

**Tests:**
- `tests/integration/api/test_incidents_api.py`
- `tests/contract/test_openapi_incidents.py` — verify schema matches

**Verification:**

```bash
uv run uvicorn aegis.main:app --reload
# Open http://127.0.0.1:8000/docs
uv run pytest tests/integration/api/ tests/contract/ -v
```

**Done checklist:**
- [ ] All four endpoints work via `/docs`
- [ ] OpenAPI spec generated automatically
- [ ] Error format consistent
- [ ] Integration tests pass

---

### Step 1.9 — Authentication and RBAC

| | |
|---|---|
| **Goal** | All endpoints (except `/health`) require JWT; roles enforced |
| **Why** | [FR-070–072](requirements/functional-requirements.md) · [Threat model THR-001, THR-011](security/threat-model.md) · [NFR-030](requirements/non-functional-requirements.md) |
| **Documentation** | [Threat model §5 Spoofing](security/threat-model.md) · [System boundaries §6](architecture/system-boundaries.md) · [Risk register RISK-002](requirements/risk-register.md) |
| **Implements** | FR-070, FR-071, FR-072, NFR-030, NFR-033 |

**Files to create:**

```text
src/aegis/domain/auth/enums.py              # Role: viewer, engineer, approver, admin
src/aegis/infrastructure/auth/jwt.py        # token create/verify
src/aegis/api/dependencies.py               # get_current_user, require_role
src/aegis/api/auth/router.py                # POST /api/v1/auth/token (dev login)
```

**Role permissions (v0.2):**

| Role | Create incident | List/Get | Transition state |
|---|---|---|---|
| `viewer` | ✗ | ✓ | ✗ |
| `engineer` | ✓ | ✓ | ✓ |
| `approver` | ✓ | ✓ | ✓ |
| `admin` | ✓ | ✓ | ✓ |

**Best practices:**
- JWT secret from env var `AEGIS_JWT_SECRET` — never hardcoded ([THR-013](security/threat-model.md))
- Short token expiry (e.g. 1 hour)
- Dev-only login endpoint for local testing; document that production uses IdP later

**Do NOT:**
- Implement approver workflow for remediation (v0.9 — FR-073)

**Tests:**
- `tests/integration/api/test_auth.py`
- `tests/security/test_rbac_incidents.py`

**Verification:**

```bash
uv run pytest tests/integration/api/test_auth.py tests/security/ -v
# Verify 401 without token, 403 with wrong role
```

**Done checklist:**
- [ ] Unauthenticated requests return 401
- [ ] Viewer cannot create or transition
- [ ] Engineer can create and transition
- [ ] Security tests pass

---

### Step 1.10 — v0.2 quality gate and release checklist

| | |
|---|---|
| **Goal** | v0.2 is complete, tested, and documented |
| **Documentation** | [NFR-051–055](requirements/non-functional-requirements.md) · [SLO-001, SLO-002](requirements/slos-and-slis.md) |

**Verification (full suite):**

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest -v
```

**v0.2 FR completion checklist:**

| FR | Description | Step |
|---|---|---|
| FR-001 | Ingest incident signals | 1.8 |
| FR-002 | Unique ID + lifecycle | 1.5, 1.6 |
| FR-003 | Six states | 1.5 |
| FR-004 | Transition timestamps | 1.5, 1.6 |
| FR-005 | Service, severity, owner | 1.5 |
| FR-006 | Manual creation via API | 1.8 |
| FR-009 | List and filter | 1.7, 1.8 |
| FR-070 | Token auth | 1.9 |
| FR-071 | RBAC | 1.9 |
| FR-072 | Four roles | 1.9 |
| FR-110 | REST API | 1.8 |
| FR-111 | OpenAPI | 1.8 |
| FR-112 | Health check | 0.1 ✓ |

**Done checklist:**
- [ ] All v0.2 P0 FRs implemented
- [ ] Full test suite passes
- [ ] Lint, format, mypy pass
- [ ] Update CHANGELOG or release notes (optional)
- [ ] Git tag `v0.2.0` (when ready)

---

## Phase 2 — v0.3 Production simulator

**Release goal:** Synthetic multi-service environment that generates incidents for AEGIS to consume.

**Start after:** Phase 1 complete.

| Step | Goal | Key FRs | Key docs |
|---|---|---|---|
| 2.1 | Simulator service skeleton in `apps/simulator/` | FR-080 | [Product vision §9](product/product-vision.md) |
| 2.2 | Model 5 services (user, order, payment, inventory, notification) | FR-080 | [Platform overview §13](architecture/platform-overview.md) |
| 2.3 | Generate logs, metrics, traces | FR-081 | [FR-080–084](requirements/functional-requirements.md) |
| 2.4 | Configurable failure scenarios | FR-082, FR-083 | [Product vision](product/product-vision.md) |
| 2.5 | Webhook emission to AEGIS API | FR-084, FR-113 | [Incident flow § Phase 1](architecture/incident-flow.md) |
| 2.6 | Incident deduplication in AEGIS | FR-007 | [Incident flow](architecture/incident-flow.md) |

**Why before RAG/agents:** You need realistic data to test against ([Risk register RISK-007](requirements/risk-register.md)).

---

## Phase 3 — v0.4 RAG platform

**Release goal:** Ingest documentation, index in OpenSearch, retrieve with citations.

| Step | Goal | Key FRs | Key docs |
|---|---|---|---|
| 3.1 | OpenSearch local setup (Docker) | FR-040 | [Platform overview §11](architecture/platform-overview.md) |
| 3.2 | Document ingestion pipeline (parse, chunk, metadata) | FR-040, FR-042 | [System boundaries §4 RAG boundary](architecture/system-boundaries.md) |
| 3.3 | Bedrock Titan embeddings | FR-040 | [ADR-004](adr/ADR-004-aws-bedrock.md) |
| 3.4 | Index to OpenSearch (vector + keyword) | FR-043 | [Platform overview §11](architecture/platform-overview.md) |
| 3.5 | Retrieval API with citations | FR-044, FR-042 | [FR-040–045](requirements/functional-requirements.md) |
| 3.6 | Re-indexing on document change | FR-045 | [FR-045](requirements/functional-requirements.md) |
| 3.7 | Index historical incidents | FR-041 | [Incident flow § Phase 6](architecture/incident-flow.md) |

**Why before agents:** Knowledge Agent needs RAG ([Platform overview §8](architecture/platform-overview.md)).

---

## Phase 4 — v0.5 Multi-agent investigation

**Release goal:** Automated investigation from incident open to RCA report.

| Step | Goal | Key FRs | Key docs |
|---|---|---|---|
| 4.1 | EventBridge + SQS local setup (LocalStack) | FR-020 | [ADR-003](adr/ADR-003-event-driven-investigation.md) |
| 4.2 | Investigation worker (async consumer) | FR-020 | [Platform overview §9](architecture/platform-overview.md) |
| 4.3 | LangGraph orchestrator skeleton | FR-021 | [Platform overview §8](architecture/platform-overview.md) |
| 4.4 | Incident Commander agent | FR-021 | [Incident flow § Phase 2](architecture/incident-flow.md) |
| 4.5 | Observability + Code + Knowledge agents | FR-010–016 | [Platform overview §8](architecture/platform-overview.md) |
| 4.6 | Evidence model + storage | FR-017, FR-018 | [Platform overview §6](architecture/platform-overview.md) |
| 4.7 | Secrets redaction pipeline | FR-019 | [Threat model THR-009](security/threat-model.md) |
| 4.8 | RCA agent + Bedrock integration | FR-030–035 | [ADR-004](adr/ADR-004-aws-bedrock.md) |
| 4.9 | Investigation progress API | FR-022 | [FR-020–028](requirements/functional-requirements.md) |
| 4.10 | Notifications (RCA ready, escalation) | FR-027, FR-028 | [Incident flow § Phase 3](architecture/incident-flow.md) |
| 4.11 | Post-incident report | FR-101 | [Incident flow § Phase 6](architecture/incident-flow.md) |

---

## Phase 5 — v0.6 Tool gateway & MCP

**Release goal:** All agent tools pass through policy-enforced gateway.

| Step | Goal | Key FRs | Key docs |
|---|---|---|---|
| 5.1 | Tool gateway core (allow/deny/log) | FR-060, FR-064, FR-067 | [Platform overview §10](architecture/platform-overview.md) |
| 5.2 | Policy rule model + admin API | FR-066 | [Threat model §7](security/threat-model.md) |
| 5.3 | Agent service accounts + scoped permissions | FR-074 | [FR-074](requirements/functional-requirements.md) |
| 5.4 | Tool implementations (`tools/`) | FR-060 | [System boundaries §3](architecture/system-boundaries.md) |
| 5.5 | MCP server exposure | FR-065 | [Platform overview §10](architecture/platform-overview.md) |
| 5.6 | Immutable audit log | FR-100, FR-062 | [ADR-002](adr/ADR-002-postgresql.md) · [THR-004](security/threat-model.md) |
| 5.7 | Rate limiting | FR-063 | [NFR-043](requirements/non-functional-requirements.md) |
| 5.8 | Security tests (prompt injection, tool abuse) | — | [Threat model §10](security/threat-model.md) |

---

## Phase 6 — v0.7 AWS deployment

**Release goal:** Production infrastructure on AWS.

| Step | Goal | Key docs |
|---|---|---|
| 6.1 | AWS CDK project in `infrastructure/cdk/` | [Platform overview §12](architecture/platform-overview.md) |
| 6.2 | VPC, subnets, security groups | [Platform overview §12](architecture/platform-overview.md) |
| 6.3 | RDS PostgreSQL | [ADR-002](adr/ADR-002-postgresql.md) |
| 6.4 | ECS/Fargate for API + worker | [ADR-001](adr/ADR-001-modular-monolith.md) |
| 6.5 | OpenSearch domain | [Platform overview §12](architecture/platform-overview.md) |
| 6.6 | EventBridge + SQS | [ADR-003](adr/ADR-003-event-driven-investigation.md) |
| 6.7 | Bedrock VPC endpoint | [ADR-004](adr/ADR-004-aws-bedrock.md) |
| 6.8 | Secrets Manager, encryption at rest | [NFR-064](requirements/non-functional-requirements.md) · [THR-013](security/threat-model.md) |
| 6.9 | GitHub Actions CI/CD pipeline | README CI/CD section |

---

## Phase 7 — v0.8 Observability & evaluation

| Step | Goal | Key FRs | Key docs |
|---|---|---|---|
| 7.1 | Structured JSON logging + request IDs | NFR-040, NFR-041 | [NFR §5](requirements/non-functional-requirements.md) |
| 7.2 | OpenTelemetry tracing | NFR-042 | [Platform overview §2](architecture/platform-overview.md) |
| 7.3 | CloudWatch metrics + alarms | NFR-043, NFR-044 | [SLOs](requirements/slos-and-slis.md) |
| 7.4 | Golden incident dataset | FR-090 | [Product vision §10](product/product-vision.md) |
| 7.5 | Evaluation pipeline (RCA accuracy, etc.) | FR-091–094 | [Risk register RISK-001](requirements/risk-register.md) |

---

## Phase 8 — v0.9 Controlled remediation

| Step | Goal | Key FRs | Key docs |
|---|---|---|---|
| 8.1 | Remediation recommendation model | FR-050, FR-051, FR-052 | [Threat model §7](security/threat-model.md) |
| 8.2 | Approval request workflow | FR-057, FR-058, FR-059 | [Incident flow § Phase 4](architecture/incident-flow.md) |
| 8.3 | Approver notifications | FR-029 | [FR-029](requirements/functional-requirements.md) |
| 8.4 | Execute approved actions via gateway | FR-053, FR-054 | [Platform overview §10](architecture/platform-overview.md) |
| 8.5 | Verification agent | FR-055, FR-056 | [Incident flow § Phase 5](architecture/incident-flow.md) |
| 8.6 | RBAC for approver role on remediation | FR-073 | [FR-073](requirements/functional-requirements.md) |

---

## 15. Traceability quick reference

When implementing any feature, fill in this chain:

```text
Product vision goal
    ↓
Functional requirement (FR-xxx)
    ↓
Non-functional constraint (NFR-xxx)
    ↓
Architecture decision (ADR-xxx)
    ↓
Threat/risk (THR-xxx / RISK-xxx)
    ↓
Code location (src/aegis/...)
    ↓
Test location (tests/...)
```

### v0.2 traceability example

```text
Goal:     Engineers manage incidents via API (product-vision §7)
FR:       FR-002, FR-003, FR-009
NFR:      NFR-011 (API latency), NFR-030 (auth)
ADR:      ADR-001 (layering), ADR-002 (PostgreSQL)
Threat:   THR-005 (tampering), THR-011 (info disclosure)
Code:     domain/incidents/ → application/incidents/ → api/incidents/
Tests:    tests/unit/domain/ + tests/integration/api/
```

---

## 16. Per-step template

Copy this template when you start any new step:

```markdown
## Step X.Y — [Title]

| | |
|---|---|
| **Goal** | |
| **Why** | |
| **Documentation** | |
| **Implements** | |
| **Files** | |
| **What to build** | |
| **Best practices** | |
| **Do NOT** | |
| **Tests** | |
| **Verification** | |

**Done checklist:**
- [ ] ...
```

---

## Related documents

- [Documentation index](README.md)
- [Functional requirements](requirements/functional-requirements.md) — primary build checklist
- [Platform overview](architecture/platform-overview.md) — visual architecture
- [Product vision](product/product-vision.md) — why we're building this

---

## Next action

**Start here:** [Step 1.1 — Create layered package structure](#step-11--create-layered-package-structure)

When ready, ask: *"Implement Step 1.1"* and we will code it together with full engineering reasoning.
