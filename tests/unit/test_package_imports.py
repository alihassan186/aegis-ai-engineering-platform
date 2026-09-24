"""Verify layered packages import cleanly and respect ADR-001 boundaries."""

from __future__ import annotations

import ast
from pathlib import Path

from aegis.core.protocols import (
    CodeSearch,
    Embedder,
    EventPublisher,
    EvidenceRepository,
    IncidentRepository,
    InvestigationProgressRepository,
    InvestigationRunner,
    KnowledgeHit,
    KnowledgeStore,
    LlmClient,
    NotificationRepository,
    Notifier,
    ObservabilitySource,
    ProcessedEventStore,
    RcaRepository,
)
from aegis.shared.exceptions import DomainError, NotFoundError, ValidationError

_FORBIDDEN_FOR_DOMAIN = (
    "aegis.infrastructure",
    "aegis.application",
    "fastapi",
    "sqlalchemy",
    "langgraph",
    "langchain",
    "langchain_core",
    "boto3",
    "opensearchpy",
)
_FORBIDDEN_FOR_APPLICATION = (
    "aegis.infrastructure",
    "fastapi",
    "sqlalchemy",
    "boto3",
    "opensearchpy",
)


def _imported_modules(package_dir: Path) -> set[str]:
    names: set[str] = set()
    for py_file in package_dir.rglob("*.py"):
        tree = ast.parse(py_file.read_text(encoding="utf-8"))
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                names.update(alias.name for alias in node.names)
            elif isinstance(node, ast.ImportFrom) and node.module:
                names.add(node.module)
    return names


def _starts_with_any(module: str, prefixes: tuple[str, ...]) -> bool:
    return any(module == prefix or module.startswith(f"{prefix}.") for prefix in prefixes)


def test_layers_import_without_circular_dependencies() -> None:
    import aegis.application
    import aegis.core
    import aegis.domain
    import aegis.infrastructure
    import aegis.shared

    assert aegis.domain.__file__ is not None
    assert aegis.application.__file__ is not None
    assert aegis.infrastructure.__file__ is not None
    assert aegis.shared.__file__ is not None
    assert aegis.core.__file__ is not None


def test_domain_does_not_import_infrastructure_or_frameworks() -> None:
    import aegis.domain

    domain_dir = Path(aegis.domain.__file__).resolve().parent
    imports = _imported_modules(domain_dir)
    forbidden = [module for module in imports if _starts_with_any(module, _FORBIDDEN_FOR_DOMAIN)]
    assert forbidden == []


def test_application_does_not_import_infrastructure_or_frameworks() -> None:
    import aegis.application

    application_dir = Path(aegis.application.__file__).resolve().parent
    imports = _imported_modules(application_dir)
    forbidden = [
        module for module in imports if _starts_with_any(module, _FORBIDDEN_FOR_APPLICATION)
    ]
    assert forbidden == []


def test_exception_hierarchy() -> None:
    assert issubclass(NotFoundError, DomainError)
    assert issubclass(ValidationError, DomainError)
    assert issubclass(DomainError, Exception)


def test_incident_repository_is_a_protocol() -> None:
    assert getattr(IncidentRepository, "_is_protocol", False)


def test_embedder_is_a_protocol() -> None:
    assert getattr(Embedder, "_is_protocol", False)


def test_knowledge_store_is_a_protocol() -> None:
    assert getattr(KnowledgeStore, "_is_protocol", False)
    assert KnowledgeHit.__dataclass_fields__


def test_event_publisher_is_a_protocol() -> None:
    assert getattr(EventPublisher, "_is_protocol", False)


def test_processed_event_store_is_a_protocol() -> None:
    assert getattr(ProcessedEventStore, "_is_protocol", False)


def test_investigation_runner_is_a_protocol() -> None:
    assert getattr(InvestigationRunner, "_is_protocol", False)


def test_observability_and_code_ports_are_protocols() -> None:
    assert getattr(ObservabilitySource, "_is_protocol", False)
    assert getattr(CodeSearch, "_is_protocol", False)


def test_evidence_repository_is_a_protocol() -> None:
    assert getattr(EvidenceRepository, "_is_protocol", False)


def test_llm_client_is_a_protocol() -> None:
    assert getattr(LlmClient, "_is_protocol", False)


def test_rca_repository_is_a_protocol() -> None:
    assert getattr(RcaRepository, "_is_protocol", False)


def test_investigation_progress_repository_is_a_protocol() -> None:
    assert getattr(InvestigationProgressRepository, "_is_protocol", False)


def test_notifier_is_a_protocol() -> None:
    assert getattr(Notifier, "_is_protocol", False)


def test_notification_repository_is_a_protocol() -> None:
    assert getattr(NotificationRepository, "_is_protocol", False)
