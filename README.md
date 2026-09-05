# AEGIS

**Autonomous Engineering & Incident Response System**

[![Python](https://img.shields.io/badge/python-3.12-blue.svg)](https://www.python.org/downloads/)
[![FastAPI](https://img.shields.io/badge/FastAPI-0.115+-009688.svg)](https://fastapi.tiangolo.com/)
[![License](https://img.shields.io/badge/license-TBD-lightgrey.svg)](#license)

AEGIS is a production-oriented AI platform for investigating production incidents, synthesizing multi-source evidence, producing grounded root cause analysis, and supporting controlled engineering remediation under explicit policy and human oversight.

---

## Table of contents

- [About](#about)
- [Problem](#problem)
- [How AEGIS works](#how-aegis-works)
- [Core capabilities](#core-capabilities)
- [Architecture](#architecture)
- [Agent model](#agent-model)
- [Technology stack](#technology-stack)
- [Repository layout](#repository-layout)
- [Getting started](#getting-started)
- [Configuration](#configuration)
- [Development](#development)
- [Testing & quality](#testing--quality)
- [Documentation](#documentation)
- [Security](#security)
- [Contributing](#contributing)
- [License](#license)

---

## About

Modern production systems generate vast amounts of operational data — logs, metrics, traces, deployment events, code changes, and runbooks — yet incident response still depends heavily on manual correlation across disconnected tools.

AEGIS addresses this by providing an AI-native investigation layer that:

- Ingests incident signals from observability and deployment systems
- Retrieves and correlates evidence across operational and engineering sources
- Produces evidence-backed root cause analysis with citations
- Recommends remediation actions classified by risk
- Enforces policy, authorization, and human approval before any write action
- Verifies outcomes and captures learnings for future incidents

The platform is built for teams who need **production-grade reliability, security, and auditability** — not ad-hoc LLM experimentation.

---

## Problem

During a production incident, engineers typically must:

1. Triage alerts across monitoring dashboards
2. Search logs and traces manually
3. Inspect recent deployments and configuration changes
4. Search code and documentation for relevant context
5. Correlate findings into a root cause hypothesis
6. Propose and execute remediation — often under time pressure

This process is slow, error-prone, and heavily dependent on institutional knowledge. Critical context is scattered, reasoning is rarely captured, and similar incidents are often re-investigated from scratch.

AEGIS is designed to compress investigation time while increasing the rigor, traceability, and safety of every step.

---

## How AEGIS works

```text
Production System
       │
       ▼
 Incident / Alert
       │
       ▼
┌──────────────────────────────────────────────────────────────┐
│                            AEGIS                             │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐  ┌──────────────────┐   │
│  │ Observability │  │     Code     │  │    Knowledge     │   │
│  │   evidence    │  │   analysis   │  │    retrieval     │   │
│  └──────┬───────┘  └──────┬───────┘  └────────┬─────────┘   │
│         └─────────────────┼───────────────────┘              │
│                           ▼                                  │
│                 Evidence collection                          │
│                           │                                  │
│                           ▼                                  │
│              Root cause analysis (RCA)                       │
│                           │                                  │
│                           ▼                                  │
│              Remediation recommendation                      │
│                           │                                  │
│                           ▼                                  │
│         Policy evaluation / human approval                   │
│                           │                                  │
│              ┌────────────┴────────────┐                     │
│              ▼                         ▼                     │
│         Controlled action         Audit & learning           │
└──────────────────────────────────────────────────────────────┘
       │
       ▼
 Incident resolution & knowledge retention
```

Each stage produces structured, auditable output. Agents operate through governed tools — never with unrestricted infrastructure access.

---

## Core capabilities

### Incident investigation

Correlate signals from logs, metrics, traces, alarms, and service health checks to build a structured evidence graph for each incident.

### Retrieval-augmented analysis (RAG)

Search across engineering documentation, runbooks, architecture records, historical incidents, and source code to ground analysis in verifiable context.

### Multi-agent orchestration

Specialized agents collaborate under an orchestration layer — planning investigations, delegating evidence collection, synthesizing findings, and proposing next steps.

### Policy-enforced remediation

Actions are classified by risk. Read operations are broadly permitted; write operations require authorization; destructive operations are denied by default.

### Evaluation & benchmarking

Investigation quality is measured against golden incident datasets — covering RCA accuracy, evidence precision, retrieval recall, tool selection, latency, and cost.

### Observability

Structured logging, metrics, distributed tracing, and agent execution telemetry provide full visibility into platform behavior in production.

---

## Architecture

AEGIS follows a **modular monolith** architecture with explicit domain boundaries, evolving toward event-driven processing as scale demands.

```text
┌─────────────────────────────────────────────────────────────────┐
│                         API Layer (FastAPI)                     │
├─────────────────────────────────────────────────────────────────┤
│  Application Layer   │  Use cases, workflows, orchestration     │
├─────────────────────────────────────────────────────────────────┤
│  Domain Layer        │  Incidents, evidence, RCA, remediation   │
├─────────────────────────────────────────────────────────────────┤
│  Infrastructure      │  PostgreSQL, Redis, Bedrock, OpenSearch  │
├─────────────────────────────────────────────────────────────────┤
│  Tool Gateway        │  MCP tools, policy enforcement, audit    │
└─────────────────────────────────────────────────────────────────┘
```

### Event-driven processing

Incident workflows are designed to run asynchronously via message queues and event routing:

```text
Incident Detected → EventBridge → SQS → Investigation Workflow → Agents
```

This model supports retries, dead-letter queues, idempotent processing, and horizontal scaling under load.

### Production simulator

AEGIS includes a simulated production environment — a multi-service application ecosystem that generates realistic logs, metrics, traces, deployments, and failure scenarios for development and evaluation.

---

## Agent model

AEGIS uses specialized agents, each responsible for a bounded domain:

| Agent | Responsibility |
|---|---|
| **Incident Commander** | Orchestrates investigation planning and agent coordination |
| **Observability Agent** | Queries logs, metrics, traces, and alarms |
| **Code Agent** | Searches repositories, inspects diffs, reviews deployment history |
| **Knowledge Agent** | Retrieves runbooks, ADRs, architecture docs, and past incidents |
| **RCA Agent** | Synthesizes evidence into grounded root cause analysis |
| **Remediation Agent** | Proposes safe, policy-compliant remediation steps |
| **Deployment Agent** | Manages controlled deployment actions |
| **Verification Agent** | Confirms whether remediation resolved the incident |

Agents invoke tools through a **gateway layer** that enforces authorization, rate limits, and audit logging before any action reaches external systems.

---

## Technology stack

| Layer | Technologies |
|---|---|
| **Language & runtime** | Python 3.12, AsyncIO |
| **API framework** | FastAPI, Pydantic, Uvicorn |
| **Data & persistence** | PostgreSQL, SQLAlchemy, Alembic, Redis |
| **Search & retrieval** | OpenSearch, hybrid retrieval, reranking |
| **AI & agents** | Amazon Bedrock, LangGraph, MCP, structured outputs, guardrails |
| **Cloud infrastructure** | AWS (ECS/Fargate, RDS, S3, SQS, EventBridge, CloudWatch, KMS) |
| **Infrastructure as code** | AWS CDK |
| **Observability** | OpenTelemetry, structured logging, CloudWatch |
| **Containerization** | Docker |
| **CI/CD** | GitHub Actions |
| **Quality** | pytest, ruff, mypy, security tests, GenAI evaluation benchmarks |

---

## Repository layout

```text
aegis-ai-engineering-platform/
├── src/aegis/                  # Core application package
│   ├── main.py                 # FastAPI entry point
│   ├── config/                 # Application settings
│   ├── domain/                 # Domain models and business rules
│   ├── application/            # Use cases and orchestration
│   ├── infrastructure/         # External system integrations
│   ├── core/                   # Shared primitives
│   └── shared/                 # Cross-cutting utilities
├── agents/                     # Specialized agent implementations
│   ├── incident_commander/
│   ├── observability/
│   ├── code/
│   ├── knowledge/
│   ├── rca/
│   └── remediation/
├── apps/                       # Application services
│   ├── api/                    # HTTP API service
│   ├── frontend/               # Web interface
│   └── simulator/              # Production environment simulator
├── services/                   # Domain microservices
│   ├── incident/
│   ├── investigation/
│   ├── approval/
│   └── deployment/
├── mcp/                        # MCP tool servers and gateway
├── tools/                      # Agent tool implementations
├── evaluation/                 # Benchmarks, datasets, and metrics
├── infrastructure/cdk/         # AWS CDK infrastructure definitions
├── docs/                       # Architecture docs, ADRs, runbooks
├── tests/                      # Unit, integration, contract, e2e, security
├── config/                     # Environment configuration
├── scripts/                    # Developer and operational scripts
└── docker/                     # Container definitions
```

---

## Getting started

### Prerequisites

| Requirement | Version |
|---|---|
| Python | 3.12 |
| [uv](https://docs.astral.sh/uv/getting-started/installation/) | Latest |
| Git | 2.x+ |
| Docker | 24+ (local PostgreSQL + OpenSearch) |

### Installation

```bash
git clone git@github.com:alihassan186/aegis-ai-engineering-platform.git
cd aegis-ai-engineering-platform
uv sync --group dev
```

### Configuration

```bash
cp config/.env.example .env
```

See [Configuration](#configuration) for the full reference.

### Local PostgreSQL

Port **5434** is used on the host so AEGIS does not collide with other local Postgres containers on 5432/5433.

```bash
cp docker/.env.example docker/.env
sudo bash scripts/docker-up.sh
```

That script deletes leftover AEGIS containers first. **docker-compose 1.29 + Docker 29 cannot recreate containers** (`KeyError: 'ContainerConfig'`). Never run `up -d` against existing AEGIS containers after a compose change; remove them first.

Manual equivalent:

```bash
sudo docker rm -f aegis-postgres aegis-pgadmin aegis-opensearch aegis-opensearch-dashboards
sudo docker ps -aq --filter name=aegis-postgres --filter name=aegis-pgadmin --filter name=aegis-opensearch | xargs -r sudo docker rm -f
sudo docker volume rm docker_aegis_pgadmin_data
sudo docker-compose -f docker/docker-compose.yml --project-directory docker up -d
```

`Permission denied` on the Docker socket: keep using `sudo`, or `sudo usermod -aG docker "$USER"` and log out/in.

The API URL is `postgresql+asyncpg://aegis:aegis@127.0.0.1:5434/aegis`.

pgAdmin: [http://127.0.0.1:5051](http://127.0.0.1:5051) — login `admin@example.com` / `admin`.  
Register a server with host `postgres`, port `5432`, database/user/password `aegis`. Do not use `127.0.0.1` as the host inside pgAdmin.

### Local OpenSearch

Port **9200** is the OpenSearch HTTP port (do not collide with 5434 / 8000 / 8001). The same `scripts/docker-up.sh` start brings up a **single-node** container with the security plugin disabled (local only). It creates an empty index `aegis-knowledge`. No documents are ingested in Step 3.1.

```bash
# already done if you ran docker-up.sh above
curl -s http://127.0.0.1:9200/_cluster/health
curl -s http://127.0.0.1:9200/aegis-knowledge
```

Set `AEGIS_OPENSEARCH_URL=http://127.0.0.1:9200` in the repo-root `.env` so AEGIS can reach the cluster. Leave it empty in CI; integration tests skip when the URL is unset.

**OpenSearch Dashboards** (local GUI, no login): [http://127.0.0.1:5601](http://127.0.0.1:5601).  
Menu → **Dev Tools** → Console to run `_cat/indices`, `_search`, `_count`. After ingest (Step 3.4), **Discover** → create an index pattern `aegis-knowledge`. This is not pgAdmin — Postgres stays at [http://127.0.0.1:5051](http://127.0.0.1:5051).

Linux: if the OpenSearch container exits on start, raise the mmap limit once: `sudo sysctl -w vm.max_map_count=262144`. Production Amazon OpenSearch is Phase 6.

### Database migrations

Schema changes go through Alembic (NFR-061). The first revision is an empty baseline; incident tables arrive in Step 1.6.

```bash
uv run alembic upgrade head
uv run alembic current
```

`AEGIS_DATABASE_URL` overrides the local URL in `alembic.ini`.

### Run the API

```bash
uv run uvicorn aegis.main:app --reload
```

Incident routes need `AEGIS_DATABASE_URL` and a Bearer JWT (`AEGIS_JWT_SECRET`). Copy `config/.env.example` to `.env` at the repo root (the app loads it on startup). Postgres must already be running on port 5434.

`POST /api/v1/auth/token` is a **development/test login only**. Production authenticates through an identity provider; that route is not registered when `AEGIS_ENV=production`.

| Endpoint | URL |
|---|---|
| Health check | [http://127.0.0.1:8000/health](http://127.0.0.1:8000/health) |
| Dev token | [http://127.0.0.1:8000/api/v1/auth/token](http://127.0.0.1:8000/api/v1/auth/token) |
| Incidents API | [http://127.0.0.1:8000/api/v1/incidents](http://127.0.0.1:8000/api/v1/incidents) |
| Incident webhooks | [http://127.0.0.1:8000/api/v1/webhooks/incidents](http://127.0.0.1:8000/api/v1/webhooks/incidents) (HMAC `X-Aegis-Signature`, not JWT) |
| OpenAPI docs | [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs) |
| ReDoc | [http://127.0.0.1:8000/redoc](http://127.0.0.1:8000/redoc) |

Verify:

```bash
curl http://127.0.0.1:8000/health

TOKEN=$(curl -s http://127.0.0.1:8000/api/v1/auth/token \
  -H 'Content-Type: application/json' \
  -d '{"username":"ali","role":"engineer"}' | python3 -c "import sys,json; print(json.load(sys.stdin)['access_token'])")

curl http://127.0.0.1:8000/api/v1/incidents \
  -H "Authorization: Bearer $TOKEN"
```

In `/docs`, use **Authorize** and paste `Bearer <token>` (or the token alone, depending on the UI). `/health` stays unauthenticated.

---

## Configuration

Environment variables are loaded from `.env` or the process environment.

### Application

| Variable | Default | Description |
|---|---|---|
| `AEGIS_ENV` | `development` | Runtime environment: `development`, `test`, `production` |
| `AEGIS_DEBUG` | `false` | Enable debug mode and auto-reload |
| `AEGIS_APP_NAME` | `aegis` | Application display name |
| `AEGIS_LOG_LEVEL` | `INFO` | Logging verbosity |
| `AEGIS_DATABASE_URL` | empty | PostgreSQL URL using `postgresql+asyncpg://` (required in production) |
| `AEGIS_JWT_SECRET` | empty | HMAC secret for JWTs (required in production; never hardcode) |
| `AEGIS_JWT_EXPIRE_SECONDS` | `3600` | Access token lifetime |
| `AEGIS_WEBHOOK_SECRET` | empty | HMAC secret for `POST /api/v1/webhooks/incidents` (required in production; THR-002) |
| `AEGIS_OPENSEARCH_URL` | empty | Local OpenSearch HTTP URL (Step 3.1). Empty means RAG store unset; tests skip the cluster ping |

### Integrations

Integration settings for database, cache, AWS, Bedrock, authentication, and observability are documented in [`.env.example`](.env.example). Copy and populate values as services are configured for your environment.

> Never commit `.env` files or credentials to version control.

---

## Development

All development commands use `uv` to ensure a reproducible environment locked by `uv.lock`.

### Activate the virtual environment

```bash
source .venv/bin/activate
```

### Code quality

```bash
uv run ruff check .          # Lint
uv run ruff format .         # Format
uv run mypy src tests        # Type check
```

### Pre-commit check

Run the full quality gate before opening a pull request:

```bash
uv run ruff check . && uv run ruff format . && uv run mypy src tests && uv run pytest
```

### Branch naming

```text
main
├── feature/*      # New features
├── fix/*          # Bug fixes
├── refactor/*     # Code restructuring
├── docs/*         # Documentation
└── chore/*        # Tooling and maintenance
```

### Commit messages

Follow [Conventional Commits](https://www.conventionalcommits.org/):

```text
feat: add incident management API
fix: handle duplicate incident events
test: add RCA workflow integration tests
docs: document RAG retrieval architecture
refactor: separate domain and infrastructure layers
chore: configure project tooling
```

---

## Testing & quality

AEGIS maintains a layered testing strategy:

| Layer | Purpose |
|---|---|
| **Unit** | Business logic and isolated components |
| **Integration** | Database, cache, and external service interactions |
| **Contract** | API and tool interface contracts |
| **End-to-end** | Full incident investigation workflows |
| **Security** | Authorization, prompt injection, tool abuse |
| **Evaluation** | GenAI quality — RCA accuracy, retrieval recall, grounding |

```bash
uv run pytest                  # Run all tests
uv run pytest -v               # Verbose output
uv run pytest tests/unit       # Unit tests only
uv run pytest tests/integration  # Integration tests only
```

---

## Documentation

| Document | Location |
|---|---|
| **Implementation guide (start coding)** | [`docs/implementation-guide.md`](docs/implementation-guide.md) |
| **Platform overview (diagrams)** | [`docs/architecture/platform-overview.md`](docs/architecture/platform-overview.md) |
| Architecture decisions (ADRs) | [`docs/adr/`](docs/adr/) |
| System architecture | [`docs/architecture/`](docs/architecture/) |
| Requirements | [`docs/requirements/`](docs/requirements/) |
| API reference | [`docs/api/`](docs/api/) |
| Operational runbooks | [`docs/runbooks/`](docs/runbooks/) |
| Threat model | [`docs/security/threat-model.md`](docs/security/threat-model.md) |

Architectural decisions follow the ADR format: context, problem, decision, alternatives, trade-offs, and consequences.

---

## Security

Security is a first-class architectural concern across every layer of AEGIS.

### Principles

- **Least privilege** — Agents and services operate with minimal required permissions
- **No credential exposure** — LLMs never receive raw AWS credentials or unrestricted production access
- **Action classification** — Operations are categorized as read, low-risk write, high-risk write, or destructive
- **Human approval** — High-risk and destructive actions require explicit authorization
- **Audit logging** — All agent actions and tool invocations are recorded
- **Defense in depth** — Guardrails, input validation, and policy enforcement at the tool gateway

### Action policy

```text
READ              → Permitted
LOW-RISK WRITE    → Controlled (logged, rate-limited)
HIGH-RISK WRITE   → Requires human approval
DESTRUCTIVE       → Denied by default
```

### Reporting

Do not open public issues for security vulnerabilities. Report concerns privately to the repository maintainer.

---

## Contributing

Contributions are welcome. Please follow these guidelines:

1. **Scope** — One clearly defined problem per pull request
2. **Style** — Match existing conventions; run lint, format, and type checks
3. **Tests** — Add or update tests for all behavior changes
4. **Documentation** — Record non-obvious architectural decisions as ADRs in `docs/adr/`
5. **Review** — Ensure CI checks pass before requesting review

---

## License

License pending. See [LICENSE](LICENSE) for details once published.

---

<p align="center">
  <sub>AEGIS — Autonomous Engineering & Incident Response System</sub>
</p>
