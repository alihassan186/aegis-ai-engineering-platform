# AEGIS

**Autonomous Engineering & Incident Response System**

A platform for AI-assisted incident investigation, evidence-backed root cause analysis, and controlled engineering remediation.

| | |
|---|---|
| **Status** | Bootstrap / foundation (`v0.1.0`) |
| **Python** | 3.12 |
| **Package manager** | [uv](https://docs.astral.sh/uv/) |
| **Repository** | [github.com/alihassan186/aegis-ai-engineering-platform](https://github.com/alihassan186/aegis-ai-engineering-platform) |

---

## Overview

AEGIS is designed to help engineering teams investigate production incidents by correlating evidence from logs, metrics, traces, deployments, source code, and operational knowledge. The long-term goal is a system that can:

1. Detect and ingest incident signals
2. Collect and correlate multi-source evidence
3. Produce grounded root cause analysis (RCA)
4. Recommend remediation under policy and human-in-the-loop controls
5. Verify outcomes and capture institutional learning

**Current scope is intentionally minimal.** The repository establishes project structure, tooling, and a thin FastAPI foundation. Agents, RAG, AWS integrations, and production workflows are planned—not yet implemented.

---

## Architecture direction

AEGIS is evolving as a **modular monolith with clear boundaries**, moving toward event-driven, agent-assisted workflows only when complexity is justified.

```text
Incident / Alert
       │
       ▼
┌──────────────────────────────────────────────────┐
│                     AEGIS                        │
│  ┌─────────────┐  ┌──────────┐  ┌─────────────┐  │
│  │ Observability│  │   Code   │  │  Knowledge  │  │
│  │   evidence   │  │  search  │  │  retrieval  │  │
│  └──────┬───────┘  └────┬─────┘  └──────┬──────┘  │
│         └───────────────┼───────────────┘        │
│                         ▼                        │
│              Evidence synthesis & RCA            │
│                         │                        │
│                         ▼                        │
│         Policy / approval / remediation          │
└──────────────────────────────────────────────────┘
       │
       ▼
Resolution, verification, and incident learning
```

### Target capabilities (roadmap)

| Area | Planned technologies |
|---|---|
| API & domain logic | FastAPI, Pydantic, SQLAlchemy, PostgreSQL, Alembic, Redis |
| AI & agents | Amazon Bedrock, RAG, LangGraph, MCP, structured outputs, guardrails |
| Cloud & ops | AWS (ECS/Fargate, SQS, EventBridge, RDS, OpenSearch, CloudWatch), AWS CDK |
| Observability | OpenTelemetry, structured logging, metrics, distributed tracing |
| Quality & safety | pytest, evaluation benchmarks, security tests, human approval gates |
| Delivery | Docker, GitHub Actions, IaC |

---

## What exists today

| Component | State |
|---|---|
| FastAPI application with `/health` | Implemented |
| Environment-aware settings (`AEGIS_*`) | Implemented |
| `src/` package layout with domain layers scaffolded | Scaffolded |
| pytest, ruff, mypy tooling | Configured |
| Repository directory structure (agents, services, docs, infra) | Scaffolded (placeholders) |
| PostgreSQL, Redis, Bedrock, agents, RAG, MCP, AWS deployment | Not implemented |

---

## Repository structure

```text
aegis-ai-engineering-platform/
├── src/aegis/                 # Core application package
│   ├── main.py                # FastAPI entry point
│   ├── config/                # Settings and configuration
│   ├── domain/                # Domain models and business rules (planned)
│   ├── application/           # Use cases / orchestration (planned)
│   ├── infrastructure/        # DB, AWS, external integrations (planned)
│   ├── core/                  # Shared primitives (planned)
│   └── shared/                # Cross-cutting utilities (planned)
├── agents/                    # Specialized agent implementations (planned)
├── apps/                      # API, frontend, simulator apps (planned)
├── services/                  # Incident, investigation, deployment services (planned)
├── mcp/                       # MCP tool servers and gateways (planned)
├── evaluation/                # Benchmarks, datasets, metrics (planned)
├── infrastructure/cdk/        # AWS CDK stacks (planned)
├── docs/                      # ADRs, architecture, runbooks, threat model
├── tests/                     # Unit, integration, contract, e2e, security tests
├── config/                    # Environment configuration examples
├── scripts/                   # Operational and developer scripts (planned)
└── docker/                    # Container definitions (planned)
```

---

## Prerequisites

- **Python 3.12** (see `.python-version`)
- **[uv](https://docs.astral.sh/uv/getting-started/installation/)** for dependency and environment management
- **Git**

Optional for later phases: Docker, AWS CLI, PostgreSQL, Redis.

---

## Quick start

### 1. Clone the repository

```bash
git clone git@github.com:alihassan186/aegis-ai-engineering-platform.git
cd aegis-ai-engineering-platform
```

### 2. Install dependencies

```bash
uv sync --group dev
```

This creates `.venv/` and installs runtime and development dependencies from `uv.lock`.

### 3. Configure environment (optional)

Copy the example configuration and adjust for local development:

```bash
cp config/.env.example .env
```

Supported variables today:

| Variable | Default | Description |
|---|---|---|
| `AEGIS_ENV` | `development` | Runtime environment (`development`, `test`, `production`) |
| `AEGIS_DEBUG` | `false` | Enable debug mode and auto-reload |
| `AEGIS_APP_NAME` | `aegis` | Application display name |
| `AEGIS_LOG_LEVEL` | `INFO` | Log level |

> **Note:** Root `.env.example` documents future integration settings (database, AWS, Bedrock, etc.). Only `AEGIS_*` variables are active in the current bootstrap.

### 4. Run the API

```bash
uv run uvicorn aegis.main:app --reload
```

Verify the service:

```bash
curl http://127.0.0.1:8000/health
# {"status":"ok"}
```

Interactive API docs: [http://127.0.0.1:8000/docs](http://127.0.0.1:8000/docs)

---

## Development

All commands run through `uv` to ensure a reproducible environment.

### Run tests

```bash
uv run pytest
```

With verbose output:

```bash
uv run pytest -v
```

### Lint

```bash
uv run ruff check .
```

### Format

```bash
uv run ruff format .
```

### Type check

```bash
uv run mypy src tests
```

### Recommended pre-commit workflow

```bash
uv run ruff check . && uv run ruff format . && uv run mypy src tests && uv run pytest
```

---

## Design principles

1. **Incremental delivery** — Build foundation first; add complexity only when a real problem requires it.
2. **Evidence over speculation** — RCA and recommendations must be grounded in retrievable evidence.
3. **Least privilege** — Agents and tools operate through gated, auditable interfaces—not raw infrastructure credentials.
4. **Human in the loop** — High-risk actions require explicit approval.
5. **Observable by default** — Logs, metrics, traces, and evaluation metrics are first-class concerns.
6. **Testable AI behavior** — Retrieval quality, RCA accuracy, and safety are measured—not assumed.

Architectural decisions will be recorded as ADRs under `docs/adr/`.

---

## Roadmap

| Version | Focus |
|---|---|
| **v0.1** *(current)* | Foundation: project structure, FastAPI bootstrap, tooling |
| **v0.2** | Core backend: domain model, PostgreSQL, authentication |
| **v0.3** | Production simulator: synthetic logs, metrics, traces, failures |
| **v0.4** | RAG platform: ingestion, retrieval, citations, evaluation |
| **v0.5** | Multi-agent investigation workflows |
| **v0.6** | MCP tools and policy-enforced action gateway |
| **v0.7** | AWS production deployment (CDK, ECS, RDS, OpenSearch) |
| **v0.8** | Observability, benchmarks, and GenAI evaluation |
| **v0.9** | Controlled remediation with approval and verification |
| **v1.0** | Production-ready platform |

---

## Git workflow

Use conventional commits on feature branches:

```text
main
├── feature/*
├── fix/*
├── refactor/*
├── docs/*
└── chore/*
```

Examples:

```text
feat: add incident management API
fix: handle duplicate incident events
test: add health endpoint contract tests
docs: document RAG architecture
chore: configure project tooling
```

---

## Security

- **Never commit secrets.** Use `.env` locally; reference `config/.env.example` for safe defaults.
- Do not commit `.env`, credentials, private keys, or local database files.
- Future agent tooling will enforce read/write action classification and audit logging.

Report security concerns privately to the repository maintainer.

---

## Contributing

This is an active engineering learning project. When contributing:

1. Keep changes scoped to a single, well-defined problem.
2. Match existing code style and project structure.
3. Add or update tests for behavior changes.
4. Run lint, type check, and tests before opening a pull request.
5. Document non-obvious architectural decisions in `docs/adr/`.

---

## License

License to be determined.

---
