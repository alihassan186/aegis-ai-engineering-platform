"""Exact v0.4 RAG allowlist (24 files). Ingest refuses anything else."""

from __future__ import annotations

from pathlib import Path

# Single source of truth — do not glob src/, requirements/, or implementation-guide.
ALLOWED_RELATIVE_PATHS: tuple[str, ...] = (
    "docs/knowledge/catalog/service-map.md",
    "docs/knowledge/runbooks/notification-queue-backlog.md",
    "docs/knowledge/runbooks/order-dependency-failure.md",
    "docs/knowledge/runbooks/payment-db-exhaustion.md",
    "docs/knowledge/runbooks/payment-latency-spike.md",
    "docs/knowledge/runbooks/user-bad-deployment.md",
    "docs/knowledge/runbooks/user-memory-leak.md",
    "docs/knowledge/incidents/INC-2026-0328-user-memory-leak.md",
    "docs/knowledge/incidents/INC-2026-0412-payment-latency.md",
    "docs/knowledge/incidents/INC-2026-0422-queue-backlog.md",
    "docs/knowledge/incidents/INC-2026-0511-db-exhaustion.md",
    "docs/knowledge/incidents/INC-2026-0709-bad-deployment.md",
    "docs/knowledge/incidents/INC-2026-0814-dependency-failure.md",
    "docs/adr/ADR-001-modular-monolith.md",
    "docs/adr/ADR-002-postgresql.md",
    "docs/adr/ADR-003-event-driven-investigation.md",
    "docs/adr/ADR-004-aws-bedrock.md",
    "docs/architecture/platform-overview.md",
    "docs/architecture/system-boundaries.md",
    "docs/architecture/incident-flow.md",
    "docs/architecture/context.md",
    "docs/security/threat-model.md",
    "docs/product/product-vision.md",
    "docs/releases/v0.3.md",
)

_ALLOWED = frozenset(ALLOWED_RELATIVE_PATHS)


def repository_root() -> Path:
    return Path(__file__).resolve().parents[4]


def relative_posix(path: Path, *, repo_root: Path | None = None) -> str:
    root = (repo_root or repository_root()).resolve()
    raw = Path(path)
    if not raw.is_absolute():
        raw = root / raw
    try:
        return raw.resolve().relative_to(root).as_posix()
    except ValueError:
        return raw.resolve().as_posix()


def is_allowlisted(path: Path | str, *, repo_root: Path | None = None) -> bool:
    root = repo_root or repository_root()
    return relative_posix(Path(path), repo_root=root) in _ALLOWED


def assert_allowlisted(path: Path | str, *, repo_root: Path | None = None) -> str:
    """Return the relative posix path or raise if the file is not on the allowlist."""
    root = repo_root or repository_root()
    rel = relative_posix(Path(path), repo_root=root)
    if rel not in _ALLOWED:
        raise ValueError(f"RAG ingest refuses {rel!r}; not in the v0.4 allowlist (FR-040).")
    return rel


def iter_allowlisted_paths(*, repo_root: Path | None = None) -> tuple[Path, ...]:
    root = (repo_root or repository_root()).resolve()
    return tuple(root / rel for rel in ALLOWED_RELATIVE_PATHS)
