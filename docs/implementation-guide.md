# AEGIS Implementation Guide

**Document owner:** Engineering  
**Status:** Active  
**Last updated:** 2026-08-31

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


| Field                      | Purpose                                    |
| -------------------------- | ------------------------------------------ |
| **Goal**                   | One sentence — what works when you're done |
| **Why**                    | Business and engineering reason            |
| **Documentation**          | Exact docs that define this step           |
| **Implements**             | FR/NFR/ADR/THR IDs                         |
| **Files to create/modify** | Concrete paths in the repo                 |
| **What to build**          | Detailed implementation description        |
| **Best practices**         | Patterns to follow                         |
| **Do NOT**                 | Scope boundaries — avoid jumping ahead     |
| **Tests**                  | What to test                               |
| **Verification**           | Commands to run                            |
| **Done checklist**         | Gate before next step                      |


---



## 2. Documentation map

Use this table to know **which document answers which question** while coding.


| Question                         | Document                                                                   |
| -------------------------------- | -------------------------------------------------------------------------- |
| What should the product do?      | [Product vision](product/product-vision.md)                                |
| What must the system implement?  | [Functional requirements](requirements/functional-requirements.md)         |
| How well must it perform/behave? | [Non-functional requirements](requirements/non-functional-requirements.md) |
| What are the SLO targets?        | [SLOs and SLIs](requirements/slos-and-slis.md)                             |
| What can go wrong?               | [Risk register](requirements/risk-register.md)                             |
| How do components fit together?  | [Platform overview (diagrams)](architecture/platform-overview.md)          |
| What are the trust boundaries?   | [System boundaries](architecture/system-boundaries.md)                     |
| What is the incident lifecycle?  | [Incident flow](architecture/incident-flow.md)                             |
| What are the security threats?   | [Threat model](security/threat-model.md)                                   |
| Why modular monolith?            | [ADR-001](adr/ADR-001-modular-monolith.md)                                 |
| Why PostgreSQL?                  | [ADR-002](adr/ADR-002-postgresql.md)                                       |
| Why event-driven workflows?      | [ADR-003](adr/ADR-003-event-driven-investigation.md)                       |
| Why Bedrock?                     | [ADR-004](adr/ADR-004-aws-bedrock.md)                                      |


**Primary coding checklist:** [Functional requirements](requirements/functional-requirements.md) filtered by target version.

**Primary architecture reference while coding:** [Platform overview §3–§7](architecture/platform-overview.md).

---



## 3. Current codebase state


| Component               | Status          | Location                                 |
| ----------------------- | --------------- | ---------------------------------------- |
| FastAPI app + `/health` | Implemented     | `src/aegis/main.py`                      |
| Settings                | Implemented     | `src/aegis/config/settings.py`           |
| Domain layer            | Implemented     | `src/aegis/domain/incidents/`            |
| Application layer       | Implemented     | `src/aegis/application/incidents/`       |
| Database session        | Implemented     | `src/aegis/infrastructure/database/`     |
| PostgreSQL (Docker)     | Implemented     | `docker/` · `scripts/docker-up.sh`       |
| Alembic migrations      | Implemented     | `alembic/` (incidents schema)            |
| Incident repository     | Implemented     | `src/aegis/infrastructure/repositories/` |
| Authentication          | Implemented     | `src/aegis/api/auth/` · JWT + RBAC       |
| Incident API            | Implemented     | `src/aegis/api/` · `/api/v1/incidents`   |
| Production simulator    | Steps 2.1–2.6   | `apps/simulator/` + ingest dedup         |
| Agents, RAG, AWS        | Not implemented | —                                        |


**You are here:** Step 2.7.1 complete → next [Step 2.7.2 — Show webhook ingest on AEGIS `/docs`](#step-272--show-webhook-ingest-on-aegis-docs).

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


| Phase                                              | Version | Focus                               | Start after |
| -------------------------------------------------- | ------- | ----------------------------------- | ----------- |
| [Phase 0](#phase-0--complete-v01-foundation)       | v0.1    | Foundation                          | —           |
| [Phase 1](#phase-1--v02-core-backend)              | v0.2    | Incident model, Postgres, auth, API | Phase 0     |
| [Phase 2](#phase-2--v03-production-simulator)      | v0.3    | Synthetic failures for testing      | Phase 1     |
| [Phase 3](#phase-3--v04-rag-platform)              | v0.4    | Knowledge ingestion & retrieval     | Phase 2     |
| [Phase 4](#phase-4--v05-multi-agent-investigation) | v0.5    | Agents, evidence, RCA               | Phase 3     |
| [Phase 5](#phase-5--v06-tool-gateway--mcp)         | v0.6    | Policy, tools, audit                | Phase 4     |
| [Phase 6](#phase-6--v07-aws-deployment)            | v0.7    | AWS CDK, ECS, RDS                   | Phase 5     |
| [Phase 7](#phase-7--v08-observability--evaluation) | v0.8    | Metrics, benchmarks                 | Phase 6     |
| [Phase 8](#phase-8--v09-controlled-remediation)    | v0.9    | Approval, remediation               | Phase 7     |


---



## Phase 0 — Complete v0.1 foundation

> **Status:** Mostly complete. Run verification below. Skip to Phase 1 if all checks pass.



### Step 0.1 — Verify bootstrap


|                   |                                          |
| ----------------- | ---------------------------------------- |
| **Goal**          | Confirm dev environment works            |
| **Documentation** | [README § Getting started](../README.md) |
| **Implements**    | FR-112, NFR-055                          |


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


|                   |                                                                                                                                                                                     |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Goal**          | Empty layer directories with clear import boundaries                                                                                                                                |
| **Why**           | [ADR-001](adr/ADR-001-modular-monolith.md) requires domain/application/infrastructure separation from day one so business logic never couples to FastAPI or SQLAlchemy              |
| **Documentation** | [ADR-001 § Boundary rules](adr/ADR-001-modular-monolith.md) · [System boundaries §3](architecture/system-boundaries.md) · [Platform overview §4](architecture/platform-overview.md) |
| **Implements**    | NFR-050                                                                                                                                                                             |


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

- [x] All layer directories exist with `__init__.py`
- [x] Base exceptions defined
- [x] No circular imports
- [x] mypy passes

---



### Step 1.2 — Extend configuration for database


|                   |                                                                                                                                                                 |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Goal**          | Settings load `DATABASE_URL` from environment                                                                                                                   |
| **Why**           | [ADR-002](adr/ADR-002-postgresql.md) — PostgreSQL is the system of record; configuration must be environment-aware for local/staging/production                 |
| **Documentation** | [ADR-002 § Implementation notes](adr/ADR-002-postgresql.md) · [NFR-060](requirements/non-functional-requirements.md) · `[.env.example](../config/.env.example)` |
| **Implements**    | NFR-060, NFR-032                                                                                                                                                |


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

- [x] `DATABASE_URL` documented in `.env.example`
- [x] Settings dataclass includes database URL
- [x] Unit tests pass

---



### Step 1.3 — Add PostgreSQL via Docker Compose


|                   |                                                                                                                   |
| ----------------- | ----------------------------------------------------------------------------------------------------------------- |
| **Goal**          | Local PostgreSQL running with one command                                                                         |
| **Why**           | [ADR-002](adr/ADR-002-postgresql.md) — use same DB locally and in production; Docker avoids "works on my machine" |
| **Documentation** | [ADR-002 § Consequences](adr/ADR-002-postgresql.md) · [Platform overview §12](architecture/platform-overview.md)  |
| **Implements**    | NFR-060                                                                                                           |


**Files to create:**

```text
docker/docker-compose.yml               # postgres service
docker/.env.example                     # POSTGRES_USER, POSTGRES_PASSWORD, POSTGRES_DB
```

**What to build:**

- PostgreSQL 16 container
- Named volume for data persistence
- Port `5434` on the host mapped to Postgres `5432` in the container (avoids collisions with other local databases)
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

- [x] Postgres container starts and is healthy
- [x] Can connect with `psql` or GUI tool

---



### Step 1.4 — Add SQLAlchemy, Alembic, and database session


|                   |                                                                                                                                                           |
| ----------------- | --------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Goal**          | Application can open async DB sessions and run migrations                                                                                                 |
| **Why**           | [ADR-002](adr/ADR-002-postgresql.md) mandates SQLAlchemy 2.x async + Alembic for schema evolution                                                         |
| **Documentation** | [ADR-002](adr/ADR-002-postgresql.md) · [NFR-061](requirements/non-functional-requirements.md) · [System boundaries §5](architecture/system-boundaries.md) |
| **Implements**    | NFR-005, NFR-061                                                                                                                                          |


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

- [x] Dependencies added to `pyproject.toml` and `uv.lock`
- [x] Alembic runs successfully
- [x] Integration test connects to Postgres

---



### Step 1.5 — Implement Incident domain model


|                   |                                                                                                                                                                                                      |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Goal**          | Pure Python incident entity with state machine rules — no DB, no API                                                                                                                                 |
| **Why**           | Domain-first design ([ADR-001](adr/ADR-001-modular-monolith.md)) — business rules tested without infrastructure                                                                                      |
| **Documentation** | [FR-002, FR-003, FR-004, FR-005](requirements/functional-requirements.md) · [Incident flow §1](architecture/incident-flow.md) · [Platform overview §6 ER diagram](architecture/platform-overview.md) |
| **Implements**    | FR-002, FR-003, FR-004, FR-005                                                                                                                                                                       |


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

- [x] Incident entity with all FR-005 fields
- [x] All 6 states defined
- [x] Transition rules match [incident-flow.md](architecture/incident-flow.md)
- [x] Unit tests cover valid and invalid transitions
- [x] No infrastructure imports in domain/

---



### Step 1.6 — PostgreSQL schema and repository


|                   |                                                                                                                                                                                  |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Goal**          | Incidents persist to PostgreSQL and load back as domain entities                                                                                                                 |
| **Why**           | [ADR-002](adr/ADR-002-postgresql.md) — system of record; repository pattern keeps domain pure                                                                                    |
| **Documentation** | [ADR-002 § Schema principles](adr/ADR-002-postgresql.md) · [Platform overview §6](architecture/platform-overview.md) · [System boundaries §5](architecture/system-boundaries.md) |
| **Implements**    | FR-002, FR-004, NFR-060, NFR-061                                                                                                                                                 |


**Files to create:**

```text
src/aegis/infrastructure/database/models/incident.py    # SQLAlchemy ORM model
src/aegis/infrastructure/database/models/state_history.py
src/aegis/infrastructure/repositories/incident_repository.py
src/aegis/infrastructure/repositories/mappers.py        # ORM ↔ domain entity
alembic/versions/xxxx_create_incidents_table.py
```

**Database schema (**`incidents` **table):**

- `id` UUID PK
- `title`, `description`, `state`, `severity`, `affected_service`
- `owner_id` UUID nullable FK (users table later — nullable for now)
- `created_at`, `updated_at` timestamps
- Soft delete: `deleted_at` nullable ([ADR-002](adr/ADR-002-postgresql.md))

**Database schema (**`incident_state_history` **table):**

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

- [x] Migration creates tables with indexes on `state`, `affected_service`, `created_at`
- [x] Repository CRUD works
- [x] State history persisted on transitions
- [x] Integration tests pass against Docker Postgres

---



### Step 1.7 — Application use cases


|                   |                                                                                                                     |
| ----------------- | ------------------------------------------------------------------------------------------------------------------- |
| **Goal**          | Business operations callable without HTTP — create, get, list, transition                                           |
| **Why**           | [ADR-001](adr/ADR-001-modular-monolith.md) — application layer orchestrates domain + repositories; routes stay thin |
| **Documentation** | [System boundaries §2](architecture/system-boundaries.md) · [FR-001–009](requirements/functional-requirements.md)   |
| **Implements**    | FR-001, FR-002, FR-004, FR-006, FR-009                                                                              |


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


| Use case             | Input                                          | Output                | FR             |
| -------------------- | ---------------------------------------------- | --------------------- | -------------- |
| `CreateIncident`     | title, severity, service, description          | Incident (state=open) | FR-001, FR-006 |
| `GetIncident`        | incident_id                                    | Incident              | FR-002         |
| `ListIncidents`      | filters: state, severity, service, owner, date | list[Incident]        | FR-009         |
| `TransitionIncident` | incident_id, new_state                         | Incident              | FR-003, FR-004 |


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

- [x] All four use cases implemented
- [x] Create sets initial state `open` with timestamp
- [x] List supports all FR-009 filters
- [x] Transition delegates to domain state machine

---



### Step 1.8 — REST API routes


|                   |                                                                                                                                                                                                      |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Goal**          | HTTP API for incident operations with OpenAPI docs                                                                                                                                                   |
| **Why**           | [FR-110, FR-111](requirements/functional-requirements.md) — REST API is the primary interface; OpenAPI enables contract tests                                                                        |
| **Documentation** | [System boundaries §4 API boundary](architecture/system-boundaries.md) · [Platform overview §2](architecture/platform-overview.md) · [NFR-080, NFR-081](requirements/non-functional-requirements.md) |
| **Implements**    | FR-001, FR-006, FR-009, FR-110, FR-111                                                                                                                                                               |


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


| Method  | Path                           | Use case           | FR             |
| ------- | ------------------------------ | ------------------ | -------------- |
| `POST`  | `/api/v1/incidents`            | CreateIncident     | FR-001, FR-006 |
| `GET`   | `/api/v1/incidents`            | ListIncidents      | FR-009         |
| `GET`   | `/api/v1/incidents/{id}`       | GetIncident        | FR-002         |
| `PATCH` | `/api/v1/incidents/{id}/state` | TransitionIncident | FR-003         |


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

- [x] All four endpoints work via `/docs`
- [x] OpenAPI spec generated automatically
- [x] Error format consistent
- [x] Integration tests pass

---



### Step 1.9 — Authentication and RBAC


|                   |                                                                                                                                                                            |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Goal**          | All endpoints (except `/health`) require JWT; roles enforced                                                                                                               |
| **Why**           | [FR-070–072](requirements/functional-requirements.md) · [Threat model THR-001, THR-011](security/threat-model.md) · [NFR-030](requirements/non-functional-requirements.md) |
| **Documentation** | [Threat model §5 Spoofing](security/threat-model.md) · [System boundaries §6](architecture/system-boundaries.md) · [Risk register RISK-002](requirements/risk-register.md) |
| **Implements**    | FR-070, FR-071, FR-072, NFR-030, NFR-033                                                                                                                                   |


**Files to create:**

```text
src/aegis/domain/auth/enums.py              # Role: viewer, engineer, approver, admin
src/aegis/infrastructure/auth/jwt.py        # token create/verify
src/aegis/api/dependencies.py               # get_current_user, require_role
src/aegis/api/auth/router.py                # POST /api/v1/auth/token (dev login)
```

**Role permissions (v0.2):**


| Role       | Create incident | List/Get | Transition state |
| ---------- | --------------- | -------- | ---------------- |
| `viewer`   | ✗               | ✓        | ✗                |
| `engineer` | ✓               | ✓        | ✓                |
| `approver` | ✓               | ✓        | ✓                |
| `admin`    | ✓               | ✓        | ✓                |


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


|                   |                                                                                                                |
| ----------------- | -------------------------------------------------------------------------------------------------------------- |
| **Goal**          | v0.2 is complete, tested, and documented                                                                       |
| **Documentation** | [NFR-051–055](requirements/non-functional-requirements.md) · [SLO-001, SLO-002](requirements/slos-and-slis.md) |


**Verification (full suite):**

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests
uv run pytest -v
```

**v0.2 FR completion checklist:**


| FR     | Description              | Step     |
| ------ | ------------------------ | -------- |
| FR-001 | Ingest incident signals  | 1.8      |
| FR-002 | Unique ID + lifecycle    | 1.5, 1.6 |
| FR-003 | Six states               | 1.5      |
| FR-004 | Transition timestamps    | 1.5, 1.6 |
| FR-005 | Service, severity, owner | 1.5      |
| FR-006 | Manual creation via API  | 1.8      |
| FR-009 | List and filter          | 1.7, 1.8 |
| FR-070 | Token auth               | 1.9      |
| FR-071 | RBAC                     | 1.9      |
| FR-072 | Four roles               | 1.9      |
| FR-110 | REST API                 | 1.8      |
| FR-111 | OpenAPI                  | 1.8      |
| FR-112 | Health check             | 0.1 ✓    |


**Done checklist:**

- [x] All v0.2 P0 FRs implemented
- [x] Full test suite passes
- [x] Lint, format, mypy pass
- [x] Update CHANGELOG or release notes (optional)
- [x] Git tag `v0.2.0` (when ready)

---



## Phase 2 — v0.3 Production simulator

**Release goal:** Synthetic multi-service environment that generates incidents for AEGIS to consume.

**Architecture reference:** [Platform overview §13](architecture/platform-overview.md)

**Start after:** Phase 1 complete (Step 1.10 quality gate).

**Why before RAG/agents:** You need realistic data to test against ([Risk register RISK-007](requirements/risk-register.md)). Agents in v0.5 investigate incidents; this phase is how those incidents get created without a real production estate.


| Step | Goal                                                             | Key FRs        | Key docs                                                   |
| ---- | ---------------------------------------------------------------- | -------------- | ---------------------------------------------------------- |
| 2.1  | Simulator service skeleton in `apps/simulator/`                  | FR-080         | [Product vision §9](product/product-vision.md)             |
| 2.2  | Model 5 services (user, order, payment, inventory, notification) | FR-080         | [Platform overview §13](architecture/platform-overview.md) |
| 2.3  | Generate logs, metrics, traces                                   | FR-081         | [FR-080–084](requirements/functional-requirements.md)      |
| 2.4  | Configurable failure scenarios                                   | FR-082, FR-083 | [Product vision](product/product-vision.md)                |
| 2.5  | Webhook emission to AEGIS API                                    | FR-084, FR-113 | [Incident flow § Phase 1](architecture/incident-flow.md)   |
| 2.6  | Incident deduplication in AEGIS                                  | FR-007         | [Incident flow](architecture/incident-flow.md)             |
| 2.7  | v0.3 quality gate (do **2.7.1 → 2.7.5** in order)                | FR-007, FR-080–084, FR-113 | [RISK-007](requirements/risk-register.md)          |


**Two codebases in this phase:**

```text
apps/simulator/     → 2.1–2.5  (producer: fake estate + HTTP client)
src/aegis/          → 2.5–2.6  (consumer: webhook ingest + dedup)
```

The simulator is **inside the AEGIS system boundary** as a dev/test tool ([System boundaries §1](architecture/system-boundaries.md)). It is **not** a layer inside `src/aegis/domain`. Do not import FastAPI routes from the simulator into domain.

---



### Step 2.1 — Simulator service skeleton


|                   |                                                                                                                                          |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------- |
| **Goal**          | A runnable process under `apps/simulator/` with its own settings and health check                                                        |
| **Why**           | [FR-080](requirements/functional-requirements.md) · [Product vision §9](product/product-vision.md) (simulator is in scope as a test env) |
| **Documentation** | [Product vision §9, §11 v0.3](product/product-vision.md) · [Platform overview §4 `apps/](architecture/platform-overview.md)`             |
| **Implements**    | FR-080 (skeleton only)                                                                                                                   |


**Files to create / modify:**

```text
apps/simulator/__init__.py              # exists — keep
apps/simulator/main.py                  # process entry (FastAPI or CLI loop)
apps/simulator/config.py                # SIMULATOR_* / AEGIS_* client settings from env
apps/simulator/pyproject.toml           # only if you treat it as a separate uv project;
                                        # otherwise run it as a module from the repo root
```

**What to build:**

- A **separate process** from `uvicorn aegis.main:app`. Suggested: small FastAPI app on a different port (e.g. `127.0.0.1:8001`) with `GET /health` → `{"status":"ok","app":"simulator"}`.
- Settings from environment (same pattern as `src/aegis/config/settings.py`): no hardcoded URLs or secrets.
- Prove it starts with `uv run` from the repo root (or `uv run --package` if you split projects).

**Best practices:**

- Keep the simulator **out of** `src/aegis/domain` and `src/aegis/application` (ADR-001).
- One responsibility: later it *emits* signals; it does not *own* incident lifecycle.

**Do NOT:**

- Call the AEGIS API yet (Step 2.5)
- Generate logs/metrics/traces yet (Step 2.3)
- Model the five services yet (Step 2.2) — a single “boot” message is enough
- Add Docker Compose service unless you already need it to run; host process is enough

**Tests:**

- `tests/unit/simulator/test_health.py` — import/create the simulator app and `GET /health` (or equivalent CLI smoke test)

**Verification:**

```bash
# Example if you use FastAPI on 8001:
uv run uvicorn apps.simulator.main:app --host 127.0.0.1 --port 8001
curl http://127.0.0.1:8001/health
uv run pytest tests/unit/simulator/ -v
```

**Done checklist:**

- [x] Simulator process starts independently of AEGIS
- [x] Health (or smoke) check passes
- [x] No import of `aegis.api` or SQLAlchemy from the skeleton
- [x] Unit test passes

---



### Step 2.2 — Model five services


|                   |                                                                                                            |
| ----------------- | ---------------------------------------------------------------------------------------------------------- |
| **Goal**          | Simulator represents user, order, payment, inventory, and notification as first-class services             |
| **Why**           | [FR-080](requirements/functional-requirements.md) — multi-service ecosystem, not a single fake app         |
| **Documentation** | [Platform overview §13](architecture/platform-overview.md) (User, Order, Payment, Inventory, Notification) |
| **Implements**    | FR-080                                                                                                     |


**Files to create:**

```text
apps/simulator/services/__init__.py
apps/simulator/services/catalog.py      # ServiceId enum + metadata (name, depends_on)
apps/simulator/services/runtime.py      # in-memory status per service (healthy / failing)
```

**What to build:**

- Enum or frozen catalog matching the diagram **exactly**:
  - `user`
  - `order`
  - `payment`
  - `inventory`
  - `notification`
- Each service has: id, display name, optional `depends_on` (e.g. `order` depends on `user` + `inventory` + `payment` — keep this small and documented; do not invent a service mesh).
- API or module function: list services and their current status. Example: `GET /services` on the simulator app.

**Best practices:**

- Services are **in-process models**, not five Docker containers (out of scope for v0.3).
- Status is data (`healthy` / `degraded` / `down`), not real resource exhaustion.

**Do NOT:**

- Deploy real microservices, Kubernetes, or extra Postgres instances
- Emit webhooks or AEGIS incidents
- Implement the six failure scenarios yet (Step 2.4)

**Tests:**

- `tests/unit/simulator/test_service_catalog.py` — all five ids present; catalog is stable

**Verification:**

```bash
uv run pytest tests/unit/simulator/test_service_catalog.py -v
curl http://127.0.0.1:8001/services   # if you exposed HTTP
```

**Done checklist:**

- [x] Five services exist with the names from §13
- [x] Caller can list services and see a status
- [x] No Docker-per-service

---



### Step 2.3 — Generate logs, metrics, and traces


|                   |                                                                                                                            |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------- |
| **Goal**          | Each service can produce structured logs, a metric sample, and a trace span (synthetic)                                    |
| **Why**           | [FR-081](requirements/functional-requirements.md) — later agents need signal *shape*, not Datadog                          |
| **Documentation** | [FR-080–084](requirements/functional-requirements.md) · [Platform overview §13 outputs](architecture/platform-overview.md) |
| **Implements**    | FR-081                                                                                                                     |


**Files to create:**

```text
apps/simulator/signals/__init__.py
apps/simulator/signals/models.py        # LogRecord, MetricSample, TraceSpan (dataclasses)
apps/simulator/signals/emitter.py       # emit for one service at “now”
```

**What to build:**

- Three signal types matching §13 **Generated Signals** (logs, metrics/latency, traces). Deployment events can be a fourth optional record type if it stays a simple struct — do not build a CI system.
- Healthy tick: e.g. one log line (`INFO` request completed), one latency metric (ms), one span (`service`, `trace_id`, `span_id`, `duration_ms`).
- Sink for v0.3: **in-memory ring buffer** and/or stdout JSON. Enough to `GET /signals?service=payment` or dump last N records in tests.

**Best practices:**

- Structured fields: `timestamp`, `service`, `severity`/`name`/`value`, `trace_id`. This is what FR-081 means by “realistic,” not a real OpenTelemetry collector.
- Deterministic fixtures in tests (inject a clock).

**Do NOT:**

- Install CloudWatch, Tempo, Jaeger, or OpenSearch
- Call AEGIS
- Simulate failure modes yet (Step 2.4) — healthy traffic only
- Persist signals in AEGIS Postgres (AEGIS does not store primary telemetry — [System boundaries §1](architecture/system-boundaries.md))

**Tests:**

- `tests/unit/simulator/test_signals.py` — emit for `payment`; assert log + metric + span present

**Verification:**

```bash
uv run pytest tests/unit/simulator/test_signals.py -v
```

**Done checklist:**

- [x] All five services can emit the three signal types
- [x] Tests do not require Docker beyond existing AEGIS Postgres
- [x] No observability vendor SDKs required

---



### Step 2.4 — Configurable failure scenarios


|                   |                                                                                                                                  |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------- |
| **Goal**          | Operator can enable a named scenario; affected services emit *failing* signals                                                   |
| **Why**           | [FR-082, FR-083](requirements/functional-requirements.md) · [Product vision §11 v0.3](product/product-vision.md)                 |
| **Documentation** | [Platform overview §13 Failure Scenarios](architecture/platform-overview.md) · [FR-083](requirements/functional-requirements.md) |
| **Implements**    | FR-082, FR-083                                                                                                                   |


**Files to create:**

```text
apps/simulator/scenarios/__init__.py
apps/simulator/scenarios/catalog.py     # ScenarioId matching FR-083
apps/simulator/scenarios/engine.py      # apply scenario → service statuses + signal bias
```

**FR-083 catalog (implement all six as config, not as real faults):**


| Scenario id          | Typical affected service(s) | Signal symptoms (examples)                         |
| -------------------- | --------------------------- | -------------------------------------------------- |
| `db_exhaustion`      | `order` or `payment`        | errors `too many connections`, error-rate metric ↑ |
| `memory_leak`        | `user`                      | growing `memory_bytes` gauge, GC / OOM-style logs  |
| `latency_spike`      | `payment`                   | p99 latency high, slow spans                       |
| `bad_deployment`     | any one service             | `deployment` event + 5xx logs after a version bump |
| `queue_backlog`      | `notification`              | queue depth metric ↑, consumer lag logs            |
| `dependency_failure` | `order` (depends on others) | timeouts calling `payment` / `inventory`           |


**What to build:**

- Activate/deactivate via config or `POST /scenarios/{id}` on the simulator (dev only).
- While a scenario is active, Step 2.3 emitters **bias** logs/metrics/traces (higher error rate, higher latency). Do **not** actually leak memory or fork bombs.
- `GET /scenarios` lists ids and which is active.

**Best practices:**

- Scenario = data + rules. Same emitter, different parameters.
- One active scenario at a time in v0.3 (keeps tests simple).

**Do NOT:**

- Exhaust the real Postgres connection pool or allocate unbounded lists
- POST to AEGIS yet (Step 2.5)
- Add Kubernetes chaos / toxiproxy unless you already have it — out of v0.3 scope

**Tests:**

- `tests/unit/simulator/test_scenarios.py` — each FR-083 id exists; activating `latency_spike` increases payment latency samples vs healthy baseline

**Verification:**

```bash
uv run pytest tests/unit/simulator/test_scenarios.py -v
```

**Done checklist:**

- [x] All six FR-083 scenario ids exist
- [x] At least one scenario changes emitted signals in a test
- [x] No real resource-exhaustion side effects

---



### Step 2.5 — Webhook emission to AEGIS API


|                   |                                                                                                                                                                                           |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Goal**          | Simulator POSTs an incident **signal** to AEGIS; AEGIS creates an `open` incident (FR-001 ingest path beyond manual `/incidents`)                                                         |
| **Why**           | [FR-084](requirements/functional-requirements.md) · [FR-113](requirements/functional-requirements.md) · [Incident flow § Phase 1](architecture/incident-flow.md)                          |
| **Documentation** | [Incident flow — Signal ingestion](architecture/incident-flow.md) · [Threat model THR-002](security/threat-model.md) · [System boundaries §1 HTTP API](architecture/system-boundaries.md) |
| **Implements**    | FR-084, FR-113, FR-001 (webhook path), THR-002 (signature)                                                                                                                                |


This step touches **both** apps.

**Files to create — AEGIS (consumer):**

```text
src/aegis/api/webhooks/router.py            # POST /api/v1/webhooks/incidents
src/aegis/api/webhooks/schemas.py           # inbound signal body
src/aegis/api/webhooks/signature.py         # HMAC verify (THR-002)
src/aegis/application/incidents/ingest_signal.py
# Wire router in src/aegis/api/router.py
# Settings: AEGIS_WEBHOOK_SECRET (required in production, like JWT)
```

**Files to create — simulator (producer):**

```text
apps/simulator/aegis_client.py              # HTTP POST + HMAC sign
# Trigger: when a scenario is active, or POST /emit on the simulator
```

**Inbound signal (keep small — map into existing CreateIncident fields):**


| Field               | Maps to                                |
| ------------------- | -------------------------------------- |
| `source`            | `"simulator"`                          |
| `service`           | `affected_service`                     |
| `title` / `summary` | `title`                                |
| `severity`          | existing `Severity` enum               |
| `scenario`          | optional, for later fingerprint        |
| `fingerprint`       | optional hint; AEGIS owns dedup in 2.6 |


**What to build:**

- **AEGIS:** `POST /api/v1/webhooks/incidents` validates JSON, verifies HMAC-SHA256 over the raw body (`AEGIS_WEBHOOK_SECRET`, header e.g. `X-Aegis-Signature`), then creates an incident in state `open` via a use case (reuse `Incident.create` — do not duplicate domain rules).
- Auth: webhook authenticity is the **signature** ([THR-002](security/threat-model.md)). This route is not the human JWT login. Do not leave it open. IP allowlisting from THR-002 can wait (document as follow-up).
- **Simulator:** HTTP client posts the same body + signature to `AEGIS_BASE_URL` (e.g. `http://127.0.0.1:8000`).
- Errors: same envelope `{ error: { code, message, request_id } }`. Invalid signature → **401**.

**Best practices:**

- Shared secret only in env (`AEGIS_WEBHOOK_SECRET` / `SIMULATOR_WEBHOOK_SECRET` copy). Never commit it.
- Version the payload mentally as `incident.signal.v1` even if you do not publish SQS yet.
- Reuse application `CreateIncident` or a thin `IngestIncidentSignal` that calls the same domain create.

**Do NOT:**

- Publish `incident.opened.v1` to EventBridge/SQS (Phase 4 / ADR-003)
- Implement deduplication yet (Step 2.6) — two identical webhooks may create two incidents until 2.6
- Use `POST /api/v1/incidents` as the webhook (that stays the **manual** engineer API + JWT)
- Implement RAG, agents, or evaluation pipeline boxes from the §13 diagram

**Tests:**

- `tests/integration/api/test_webhook_ingest.py` — valid HMAC → 201 + incident exists; bad HMAC → 401
- `tests/unit/simulator/test_aegis_client.py` — signature bytes match what AEGIS verifies (can share a test helper)

**Verification:**

```bash
# Terminal 1 — AEGIS (needs AEGIS_WEBHOOK_SECRET in .env)
uv run uvicorn aegis.main:app --reload

# Terminal 2 — simulator emit (or pytest)
uv run pytest tests/integration/api/test_webhook_ingest.py tests/unit/simulator/test_aegis_client.py -v
```

**Done checklist:**

- [x] Simulator can emit one signal AEGIS accepts
- [x] Unsigned / wrong signature rejected
- [x] Created incident is `open` with correct `affected_service`
- [x] Manual `POST /api/v1/incidents` still requires JWT

---



### Step 2.6 — Incident deduplication in AEGIS


|                   |                                                                                                                          |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------ |
| **Goal**          | Two signals for the same underlying issue become **one** incident (or link to the existing one)                          |
| **Why**           | [FR-007](requirements/functional-requirements.md) · [Incident flow § Phase 1 Deduplicate](architecture/incident-flow.md) |
| **Documentation** | [Incident flow — same fingerprint](architecture/incident-flow.md)                                                        |
| **Implements**    | FR-007                                                                                                                   |


**Files to create / modify:**

```text
src/aegis/domain/incidents/fingerprint.py   # compute fingerprint from signal fields
src/aegis/application/incidents/ingest_signal.py   # lookup-or-create
src/aegis/infrastructure/repositories/incident_repository.py
src/aegis/infrastructure/database/models/incident.py   # fingerprint column if needed
alembic/versions/*_incident_fingerprint.py
src/aegis/core/protocols.py                 # get_open_by_fingerprint
```

**What to build:**

- **Fingerprint** (v0.3, keep it boring): hash or stable key from `affected_service` + `scenario` (or signal type) + optional time bucket (e.g. calendar hour UTC). Same key while an incident is still `open` (or still “active” — pick one rule and test it).
- Ingest path: if an **open** incident with that fingerprint exists → **do not** create a second row; return the existing incident (HTTP 200) and optionally record that a duplicate signal arrived (in-memory counter or a line in description — do **not** build a full evidence model).
- If none exists → create as today (201).
- Persist fingerprint on the incident row so list/get stay simple.

**Best practices:**

- Dedup is a **domain/application** rule, not “if title == title” in the router.
- Unique constraint in Postgres on `(fingerprint)` for open incidents if you can express it cleanly (partial unique index `WHERE deleted_at IS NULL AND state = 'open'` is ideal). If that is too heavy for the first slice, application-level check + a test is acceptable, then add the index in the same step if time allows.
- Manual `POST /api/v1/incidents` can omit fingerprint (null) so engineer-created incidents are not collapsed.

**Do NOT:**

- Implement FR-008 (related-incident graph)
- Soft-delete or auto-close as a substitute for dedup
- Emit EventBridge events
- Dedup closed incidents by default (a new outage after close is a **new** incident)

**Tests:**

- `tests/unit/domain/incidents/test_fingerprint.py`
- `tests/unit/application/incidents/test_ingest_signal.py` — second ingest returns same id
- `tests/integration/api/test_webhook_ingest.py` — POST twice → one row

**Verification:**

```bash
uv run pytest tests/unit/domain/incidents/test_fingerprint.py \
  tests/unit/application/incidents/test_ingest_signal.py \
  tests/integration/api/test_webhook_ingest.py -v
```

**Done checklist:**

- [x] Duplicate webhook does not create a second open incident
- [x] Distinct service/scenario still creates a new incident
- [x] Manual create without fingerprint still works
- [x] Tests pass without relying on an empty leftover `/docs` table (assert on ids you created)

---



### Step 2.7 — v0.3 quality gate


|                   |                                                                                                                                                          |
| ----------------- | -------------------------------------------------------------------------------------------------------------------------------------------------------- |
| **Goal**          | v0.3 is complete enough to feed later RAG/agent work — proven by FR traceability, `/docs`, a live demo, a green suite, and a release note                |
| **Why**           | [RISK-007](requirements/risk-register.md) — agents need repeatable incidents; do not start OpenSearch until this gate passes                              |
| **Documentation** | [RISK-007](requirements/risk-register.md) · [FR-007, FR-080–084, FR-113](requirements/functional-requirements.md) · [Incident flow § Phase 1](architecture/incident-flow.md) |
| **Implements**    | Gate for FR-007, FR-080, FR-081, FR-082, FR-083, FR-084, FR-113 (no new product features)                                                                |


This step is a **gate**, not a new feature. Implement **2.7.1 then 2.7.2 then 2.7.3 then 2.7.4 then 2.7.5**. Do not skip ahead. Do not start Phase 3 until the parent Done checklist at the bottom is complete.

**v0.3 FR map (what 2.1–2.6 already built — you verify here, you do not rebuild):**


| FR     | Description                         | Built in | Proof you will collect in 2.7                          |
| ------ | ----------------------------------- | -------- | ------------------------------------------------------ |
| FR-080 | Multi-service simulator             | 2.1–2.2  | 2.7.1 file/test paths for five services                |
| FR-081 | Logs, metrics, traces               | 2.3      | 2.7.1 `test_signals.py`                                |
| FR-082 | Configurable scenarios              | 2.4      | 2.7.1 `POST /scenarios/{id}`                           |
| FR-083 | Six named failure types             | 2.4      | 2.7.1 all six ids in catalog tests                     |
| FR-084 | Signals consumable by AEGIS         | 2.5      | 2.7.3 `POST /emit` → webhook                           |
| FR-113 | Webhook ingestion                   | 2.5      | 2.7.2 `/docs` + 2.7.3 HMAC POST                        |
| FR-007 | Deduplicate signals                 | 2.6      | 2.7.3 second emit → **200** same id                    |


**Parent Done checklist** (tick only after **all** of 2.7.1–2.7.5):

- [ ] All v0.3 FRs in the table above have a row in the 2.7.1 traceability file
- [ ] Simulator + AEGIS demo: activate a scenario → webhook → one incident visible via `/docs` and `GET /api/v1/incidents/{id}`
- [ ] Duplicate emit does not double-create
- [ ] Full test suite, lint, and mypy pass
- [ ] Git tag `v0.3.0` (when you are ready — 2.7.5)

---



#### Step 2.7.1 — Trace every v0.3 FR to code and tests


|                   |                                                                                                                         |
| ----------------- | ----------------------------------------------------------------------------------------------------------------------- |
| **Goal**          | One page lists, for each v0.3 FR, the production files and the tests that prove it                                      |
| **Why**           | [RISK-007](requirements/risk-register.md) — later RAG/eval needs to know what “a scenario incident” already is          |
| **Documentation** | [FR-007, FR-080–084, FR-113](requirements/functional-requirements.md)                                                   |
| **Implements**    | Traceability only (no behaviour change)                                                                                 |


**Files to create:**

```text
docs/releases/v0.3-fr-traceability.md
```

**What to build:**

- A markdown table with **one row per FR** in the parent map (FR-080, FR-081, FR-082, FR-083, FR-084, FR-113, FR-007).
- Columns: `FR` · `What it means in this repo` · `Primary code paths` · `Primary tests`.
- Fill paths by **inspecting the repo**, not by inventing new modules. Examples of what you should find (confirm, do not copy blindly):
  - FR-080 → `apps/simulator/main.py`, `apps/simulator/services/catalog.py`, `tests/unit/simulator/test_health.py`, `test_service_catalog.py`
  - FR-081 → `apps/simulator/signals/`, `tests/unit/simulator/test_signals.py`
  - FR-082 / FR-083 → `apps/simulator/scenarios/`, `tests/unit/simulator/test_scenarios.py` (all six ids)
  - FR-084 / FR-113 → `apps/simulator/aegis_client.py`, `src/aegis/api/webhooks/`, `tests/unit/simulator/test_aegis_client.py`, `tests/integration/api/test_webhook_ingest.py`
  - FR-007 → `src/aegis/domain/incidents/fingerprint.py`, `ingest_signal.py`, `tests/unit/domain/incidents/test_fingerprint.py`, second-ingest tests
- One short **Out of v0.3** bullet list: no RAG, no agents, no EventBridge, no FR-008 related-incident graph, no IP allowlisting.

**Best practices:**

- Paths must exist in git. If a row has no test, that is a **gap** — stop and add a test in the original step’s file, do not invent a new feature.
- Keep the page boring. This is a map, not a tutorial.

**Do NOT:**

- Re-implement 2.1–2.6
- Start OpenSearch, Bedrock, or LangGraph
- Change fingerprint, HMAC, or catalog behaviour

**Tests:**

- None new. This step is documentation. Proof is: every path in the table opens in the editor.

**Verification:**

```bash
# Every file you listed must exist, for example:
test -f apps/simulator/services/catalog.py
test -f src/aegis/api/webhooks/router.py
test -f src/aegis/domain/incidents/fingerprint.py
test -f docs/releases/v0.3-fr-traceability.md
```

**Done checklist:**

- [x] Seven FR rows filled with real paths
- [x] Out of v0.3 list present
- [x] No new runtime code in this slice

---



#### Step 2.7.2 — Show webhook ingest on AEGIS `/docs`


|                   |                                                                                                                                      |
| ----------------- | ------------------------------------------------------------------------------------------------------------------------------------ |
| **Goal**          | FastAPI Swagger UI (`/docs`) and `/openapi.json` document `POST /api/v1/webhooks/incidents` with **201** (create) and **200** (dedup) |
| **Why**           | [FR-111](requirements/functional-requirements.md) · parent checklist “one incident in `/docs`” — operators must see the ingest route |
| **Documentation** | [System boundaries §1 HTTP API](architecture/system-boundaries.md) · [FR-113](requirements/functional-requirements.md)               |
| **Implements**    | FR-111 (webhook path visible), FR-113 (documented)                                                                                   |


**Files to modify:**

```text
tests/contract/test_openapi_incidents.py    # assert webhook path + 200/201
src/aegis/api/webhooks/router.py            # only if OpenAPI is missing 200/201
```

**What to build:**

- Open `http://127.0.0.1:8000/docs` (AEGIS, not the simulator). Confirm a **webhooks** tag and `POST /api/v1/webhooks/incidents`.
- Contract test: `/openapi.json` contains that path; POST responses include `201` and `200`.
- If the route exists but OpenAPI omits `200`, add it to `responses=` on the webhook router (do not change HMAC or ingest logic).

**Best practices:**

- `/docs` is the AEGIS app on **8000**. Simulator `/docs` on 8001 is a different OpenAPI — do not confuse them.
- Webhook auth in the UI is **not** Bearer JWT. Note in the router docstring that authenticity is `X-Aegis-Signature`.

**Do NOT:**

- Put the webhook on `/api/v1/incidents` (that stays JWT + manual create)
- Remove HMAC
- Implement Try-it-out HMAC signing inside Swagger (out of scope)

**Tests:**

- `tests/contract/test_openapi_incidents.py` — webhook path present; `200` and `201` listed; existing `/docs` UI test still `200`

**Verification:**

```bash
uv run pytest tests/contract/test_openapi_incidents.py -v
# AEGIS running:
curl -s http://127.0.0.1:8000/openapi.json | python3 -c "import sys,json; p=json.load(sys.stdin)['paths']; print(p['/api/v1/webhooks/incidents']['post']['responses'].keys())"
```

**Done checklist:**

- [ ] `/docs` shows the webhook operation
- [ ] Contract test asserts `200` and `201`
- [ ] Manual `POST /api/v1/incidents` still documented separately and still JWT

---



#### Step 2.7.3 — Demo: scenario → webhook → one incident (duplicate emit stays one)


|                   |                                                                                                                                                |
| ----------------- | ---------------------------------------------------------------------------------------------------------------------------------------------- |
| **Goal**          | An operator can activate a scenario, emit once, see **one** `open` incident; emit again and get the **same id** (HTTP 200)                      |
| **Why**           | Parent checklist: live demo + FR-007 / FR-084 / FR-113 together                                                                                |
| **Documentation** | [Incident flow § Phase 1](architecture/incident-flow.md) · [FR-007](requirements/functional-requirements.md)                                   |
| **Implements**    | Proof of FR-084, FR-113, FR-007 (no new domain rules)                                                                                          |


**Files to create:**

```text
scripts/demo-v0.3.sh    # curl-only; reads secrets from the environment
```

**What to build:**

- A bash script that **fails fast** (`set -euo pipefail`) and:
  1. `GET http://127.0.0.1:8000/health` and `GET http://127.0.0.1:8001/health`
  2. `POST http://127.0.0.1:8001/scenarios/latency_spike`
  3. `POST http://127.0.0.1:8001/emit` — expect **201** from AEGIS (simulator may proxy that status)
  4. Parse incident `id` from the JSON body
  5. Dev login `POST /api/v1/auth/token` then `GET /api/v1/incidents/{id}` — `state` is `open`, `affected_service` is `payment` for `latency_spike`
  6. `POST /emit` again — expect **200** and the **same** `id`
  7. Print both ids and `exit 1` if they differ
- Script must **not** hardcode webhook/JWT secrets. Use env already required by `.env` (`AEGIS_WEBHOOK_SECRET` is used by the simulator client; token login uses `AEGIS_JWT_SECRET` on the server).
- Header comment: both processes must already be running; Postgres migrated (`uv run alembic upgrade head`).

**Best practices:**

- Assert on the **id you created**, never “table is empty” (leftover rows are normal).
- Default scenario `latency_spike` is enough. Do not loop all six in this script.

**Do NOT:**

- Auto-start uvicorn or Docker from the script (operator starts processes)
- Publish EventBridge / SQS
- Close or soft-delete the incident as part of the demo
- Call OpenSearch

**Tests:**

- Existing: `tests/integration/api/test_webhook_ingest.py` (`test_duplicate_webhooks_return_the_same_open_incident`)
- The shell script is **manual verification**, not pytest

**Verification:**

```bash
# Terminal A
uv run uvicorn aegis.main:app --host 127.0.0.1 --port 8000

# Terminal B
uv run uvicorn apps.simulator.main:app --host 127.0.0.1 --port 8001

# Terminal C (repo root, .env loaded by the apps)
bash scripts/demo-v0.3.sh
uv run pytest tests/integration/api/test_webhook_ingest.py -v
```

**Done checklist:**

- [ ] First emit creates one `open` incident
- [ ] Second emit returns the same id
- [ ] You can open `/docs`, find the incident id, and match `GET /api/v1/incidents/{id}`
- [ ] Script contains no committed secrets

---



#### Step 2.7.4 — Full suite, lint, types, and version stamp


|                   |                                                                                                      |
| ----------------- | ---------------------------------------------------------------------------------------------------- |
| **Goal**          | `ruff`, `mypy`, and `pytest` are green; AEGIS reports version **0.3.0**                              |
| **Why**           | [NFR-051–055](requirements/non-functional-requirements.md) quality bar used at the v0.2 gate (1.10) |
| **Documentation** | Same as Step 1.10                                                                                    |
| **Implements**    | Release hygiene (no new FR)                                                                          |


**Files to modify (only if needed):**

```text
pyproject.toml                 # [project] version = "0.3.0"
src/aegis/main.py              # FastAPI(version="0.3.0")
apps/simulator/main.py         # already 0.3.0 — confirm, do not invent a second scheme
```

**What to build:**

- Run the full suite below. **Fix failures** — do not skip tests, do not `--no-verify`.
- `mypy` must include **`apps`** (simulator) as well as `src` and `tests` (`pyproject.toml` `[tool.mypy] files`).
- Set the AEGIS FastAPI `version` and package version to `0.3.0` so `/docs` and OpenAPI `info.version` match the release.

**Best practices:**

- If a test fails, fix the product or the test in the step that owns it (2.1–2.6), then re-run 2.7.4. Do not disable tests.
- Do not reformat the whole repo “for fun”; only files you touch if ruff format fails.

**Do NOT:**

- Add RAG, agents, or new endpoints “while the suite is open”
- Change fingerprint or HMAC to make a test pass without a failing assertion that requires it
- Tag git yet (that is 2.7.5)

**Tests:**

- The entire `tests/` tree (the command is the test)

**Verification:**

```bash
uv run ruff check .
uv run ruff format --check .
uv run mypy src tests apps
uv run pytest -v
```

**Done checklist:**

- [ ] `ruff check` and `ruff format --check` pass
- [ ] `mypy src tests apps` passes
- [ ] `pytest -v` passes (full suite)
- [ ] OpenAPI / FastAPI version is `0.3.0`

---



#### Step 2.7.5 — RISK-007, release note, tag when ready


|                   |                                                                                                      |
| ----------------- | ---------------------------------------------------------------------------------------------------- |
| **Goal**          | Risk register and a short release note describe v0.3; you can tag `v0.3.0` when you choose           |
| **Why**           | [RISK-007](requirements/risk-register.md) review at a version gate · [NFR](requirements/non-functional-requirements.md) release notes |
| **Documentation** | [RISK-007](requirements/risk-register.md) · parent 2.7 FR map                                        |
| **Implements**    | Process / docs only                                                                                  |


**Files to create / modify:**

```text
docs/releases/v0.3.md                    # short release note (what v0.3 is / is not)
docs/requirements/risk-register.md       # RISK-007 status: simulator exists; golden RCA dataset still open
docs/implementation-guide.md             # tick 2.7.1–2.7.5 and parent Done checklist; You are here → Phase 3
docs/README.md                           # link the release note (optional, one line)
```

**What to build:**

- `docs/releases/v0.3.md`: one screen of **what shipped** (simulator, six scenarios, HMAC webhook, open-incident fingerprint) and **what did not** (RAG, agents, EventBridge, FR-008, IP allowlisting).
- RISK-007: do **not** close the risk. Set status to something like `Partial v0.3` and add a detailed subsection: simulator mitigates “no incidents to evaluate”; **golden RCA dataset** remains open until later evaluation steps.
- Point “You are here” in the implementation guide at [Phase 3 / Step 3.1](#phase-3--v04-rag-platform) only after 2.7.1–2.7.4 are done.
- Git tag **when you are ready** (you create the tag; do not force-push `main`):

```bash
git tag -a v0.3.0 -m "v0.3 production simulator, webhook ingest, open-incident dedup"
git show v0.3.0 --no-patch
```

**Best practices:**

- Tag the commit that has 2.7.1–2.7.4 merged, not an uncommitted tree.
- Do not put secrets in the release note.

**Do NOT:**

- Start Step 3.1 (OpenSearch) in the same change as the tag
- Mark RISK-007 **Closed** (golden dataset is still missing)
- Rewrite ADRs

**Tests:**

- None. Re-run 2.7.4 if you touched Python while editing docs (you should not need to).

**Verification:**

```bash
# RISK-007 still mentioned as not fully closed
grep -n "RISK-007" docs/requirements/risk-register.md
test -f docs/releases/v0.3.md
```

**Done checklist:**

- [ ] `docs/releases/v0.3.md` exists and lists out-of-scope items
- [ ] RISK-007 updated to partial (simulator yes, golden dataset no)
- [ ] Implementation guide parent 2.7 checklist ticked
- [ ] Tag `v0.3.0` created when you are ready (optional until you explicitly want it)

---




## Phase 3 — v0.4 RAG platform

**Release goal:** Ingest documentation, index in OpenSearch, retrieve with citations.


| Step | Goal                                                 | Key FRs        | Key docs                                                               |
| ---- | ---------------------------------------------------- | -------------- | ---------------------------------------------------------------------- |
| 3.1  | OpenSearch local setup (Docker)                      | FR-040         | [Platform overview §11](architecture/platform-overview.md)             |
| 3.2  | Document ingestion pipeline (parse, chunk, metadata) | FR-040, FR-042 | [System boundaries §4 RAG boundary](architecture/system-boundaries.md) |
| 3.3  | Bedrock Titan embeddings                             | FR-040         | [ADR-004](adr/ADR-004-aws-bedrock.md)                                  |
| 3.4  | Index to OpenSearch (vector + keyword)               | FR-043         | [Platform overview §11](architecture/platform-overview.md)             |
| 3.5  | Retrieval API with citations                         | FR-044, FR-042 | [FR-040–045](requirements/functional-requirements.md)                  |
| 3.6  | Re-indexing on document change                       | FR-045         | [FR-045](requirements/functional-requirements.md)                      |
| 3.7  | Index historical incidents                           | FR-041         | [Incident flow § Phase 6](architecture/incident-flow.md)               |


**Why before agents:** Knowledge Agent needs RAG ([Platform overview §8](architecture/platform-overview.md)).

---



## Phase 4 — v0.5 Multi-agent investigation

**Release goal:** Automated investigation from incident open to RCA report.


| Step | Goal                                       | Key FRs        | Key docs                                                  |
| ---- | ------------------------------------------ | -------------- | --------------------------------------------------------- |
| 4.1  | EventBridge + SQS local setup (LocalStack) | FR-020         | [ADR-003](adr/ADR-003-event-driven-investigation.md)      |
| 4.2  | Investigation worker (async consumer)      | FR-020         | [Platform overview §9](architecture/platform-overview.md) |
| 4.3  | LangGraph orchestrator skeleton            | FR-021         | [Platform overview §8](architecture/platform-overview.md) |
| 4.4  | Incident Commander agent                   | FR-021         | [Incident flow § Phase 2](architecture/incident-flow.md)  |
| 4.5  | Observability + Code + Knowledge agents    | FR-010–016     | [Platform overview §8](architecture/platform-overview.md) |
| 4.6  | Evidence model + storage                   | FR-017, FR-018 | [Platform overview §6](architecture/platform-overview.md) |
| 4.7  | Secrets redaction pipeline                 | FR-019         | [Threat model THR-009](security/threat-model.md)          |
| 4.8  | RCA agent + Bedrock integration            | FR-030–035     | [ADR-004](adr/ADR-004-aws-bedrock.md)                     |
| 4.9  | Investigation progress API                 | FR-022         | [FR-020–028](requirements/functional-requirements.md)     |
| 4.10 | Notifications (RCA ready, escalation)      | FR-027, FR-028 | [Incident flow § Phase 3](architecture/incident-flow.md)  |
| 4.11 | Post-incident report                       | FR-101         | [Incident flow § Phase 6](architecture/incident-flow.md)  |


---



## Phase 5 — v0.6 Tool gateway & MCP

**Release goal:** All agent tools pass through policy-enforced gateway.


| Step | Goal                                          | Key FRs                | Key docs                                                                   |
| ---- | --------------------------------------------- | ---------------------- | -------------------------------------------------------------------------- |
| 5.1  | Tool gateway core (allow/deny/log)            | FR-060, FR-064, FR-067 | [Platform overview §10](architecture/platform-overview.md)                 |
| 5.2  | Policy rule model + admin API                 | FR-066                 | [Threat model §7](security/threat-model.md)                                |
| 5.3  | Agent service accounts + scoped permissions   | FR-074                 | [FR-074](requirements/functional-requirements.md)                          |
| 5.4  | Tool implementations (`tools/`)               | FR-060                 | [System boundaries §3](architecture/system-boundaries.md)                  |
| 5.5  | MCP server exposure                           | FR-065                 | [Platform overview §10](architecture/platform-overview.md)                 |
| 5.6  | Immutable audit log                           | FR-100, FR-062         | [ADR-002](adr/ADR-002-postgresql.md) · [THR-004](security/threat-model.md) |
| 5.7  | Rate limiting                                 | FR-063                 | [NFR-043](requirements/non-functional-requirements.md)                     |
| 5.8  | Security tests (prompt injection, tool abuse) | —                      | [Threat model §10](security/threat-model.md)                               |


---



## Phase 6 — v0.7 AWS deployment

**Release goal:** Production infrastructure on AWS.


| Step | Goal                                     | Key docs                                                                                     |
| ---- | ---------------------------------------- | -------------------------------------------------------------------------------------------- |
| 6.1  | AWS CDK project in `infrastructure/cdk/` | [Platform overview §12](architecture/platform-overview.md)                                   |
| 6.2  | VPC, subnets, security groups            | [Platform overview §12](architecture/platform-overview.md)                                   |
| 6.3  | RDS PostgreSQL                           | [ADR-002](adr/ADR-002-postgresql.md)                                                         |
| 6.4  | ECS/Fargate for API + worker             | [ADR-001](adr/ADR-001-modular-monolith.md)                                                   |
| 6.5  | OpenSearch domain                        | [Platform overview §12](architecture/platform-overview.md)                                   |
| 6.6  | EventBridge + SQS                        | [ADR-003](adr/ADR-003-event-driven-investigation.md)                                         |
| 6.7  | Bedrock VPC endpoint                     | [ADR-004](adr/ADR-004-aws-bedrock.md)                                                        |
| 6.8  | Secrets Manager, encryption at rest      | [NFR-064](requirements/non-functional-requirements.md) · [THR-013](security/threat-model.md) |
| 6.9  | GitHub Actions CI/CD pipeline            | README CI/CD section                                                                         |


---



## Phase 7 — v0.8 Observability & evaluation


| Step | Goal                                     | Key FRs          | Key docs                                                  |
| ---- | ---------------------------------------- | ---------------- | --------------------------------------------------------- |
| 7.1  | Structured JSON logging + request IDs    | NFR-040, NFR-041 | [NFR §5](requirements/non-functional-requirements.md)     |
| 7.2  | OpenTelemetry tracing                    | NFR-042          | [Platform overview §2](architecture/platform-overview.md) |
| 7.3  | CloudWatch metrics + alarms              | NFR-043, NFR-044 | [SLOs](requirements/slos-and-slis.md)                     |
| 7.4  | Golden incident dataset                  | FR-090           | [Product vision §10](product/product-vision.md)           |
| 7.5  | Evaluation pipeline (RCA accuracy, etc.) | FR-091–094       | [Risk register RISK-001](requirements/risk-register.md)   |


---



## Phase 8 — v0.9 Controlled remediation


| Step | Goal                                  | Key FRs                | Key docs                                                   |
| ---- | ------------------------------------- | ---------------------- | ---------------------------------------------------------- |
| 8.1  | Remediation recommendation model      | FR-050, FR-051, FR-052 | [Threat model §7](security/threat-model.md)                |
| 8.2  | Approval request workflow             | FR-057, FR-058, FR-059 | [Incident flow § Phase 4](architecture/incident-flow.md)   |
| 8.3  | Approver notifications                | FR-029                 | [FR-029](requirements/functional-requirements.md)          |
| 8.4  | Execute approved actions via gateway  | FR-053, FR-054         | [Platform overview §10](architecture/platform-overview.md) |
| 8.5  | Verification agent                    | FR-055, FR-056         | [Incident flow § Phase 5](architecture/incident-flow.md)   |
| 8.6  | RBAC for approver role on remediation | FR-073                 | [FR-073](requirements/functional-requirements.md)          |


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

**Start here:** [Step 2.1 — Simulator service skeleton](#step-21--simulator-service-skeleton)

When ready, ask: *"Implement Step 2.1"* and we will code it together with full engineering reasoning.