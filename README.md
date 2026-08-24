# AEGIS

AEGIS (Autonomous Engineering & Incident Response System) is a long-term platform for AI-assisted production operations and engineering workflows.

Current project status: Bootstrap / Architecture Foundation

## Long-term goal

AEGIS is intended to evolve into a production-grade AI system for incident detection, investigation, root cause analysis, remediation guidance, and controlled operational execution. The initial scope is intentionally small and focuses on a clean architectural foundation rather than product features.

## Technology direction

The project is planned to evolve around:

- Python
- FastAPI
- PostgreSQL
- Redis
- Amazon Bedrock
- RAG
- LangGraph
- MCP
- AWS
- Docker
- AWS CDK
- GitHub Actions
- OpenTelemetry
- CloudWatch
- pytest

## Local environment

This project uses `uv` for Python environment and dependency management.

### Create and sync the environment

```bash
uv sync --group dev
```

### Activate the environment

```bash
source .venv/bin/activate
```

## Run the minimal FastAPI application

```bash
uvicorn aegis.main:app --reload
```

Then open:

- http://127.0.0.1:8000/health

## Run tests

```bash
pytest
```

## Run linting

```bash
ruff check .
```

## Run type checking

```bash
mypy src tests
```

## Notes

This repository currently contains the project foundation and a minimal health check endpoint only. Feature work, agent orchestration, AWS integrations, operational logic, and production services are intentionally not implemented yet.
