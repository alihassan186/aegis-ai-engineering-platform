"""Specialist adapters: ports in, structured evidence out. No HTTP, no OpenSearch.

Tool calls in v0.5 are direct port calls. Phase 5 wraps them in the gateway.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from aegis.application.investigation.state import (
    EVIDENCE_TEXT_CAP,
    KNOWLEDGE_MAX_CHUNKS,
    OBS_MAX_ITEMS,
    InvestigationState,
)
from aegis.application.rag.allowlist import is_allowlisted
from aegis.application.rag.retrieve import (
    Citation,
    RetrieveFilters,
    RetrieveHit,
    RetrieveResult,
)
from aegis.core.protocols import CodeHit, CodeSearch, ObservabilitySignal, ObservabilitySource

KNOWLEDGE_DOC_TYPES = ("runbook", "incident_report")
_SOURCE_SIMULATOR = "simulator"
_SOURCE_RAG = "rag"
_SOURCE_CODE = "fake_code_search"

_RUNBOOK_BY_SCENARIO: dict[str, str] = {
    "latency_spike": "docs/knowledge/runbooks/payment-latency-spike.md",
    "db_exhaustion": "docs/knowledge/runbooks/payment-db-exhaustion.md",
    "memory_leak": "docs/knowledge/runbooks/user-memory-leak.md",
    "bad_deployment": "docs/knowledge/runbooks/user-bad-deployment.md",
    "queue_backlog": "docs/knowledge/runbooks/notification-queue-backlog.md",
    "dependency_failure": "docs/knowledge/runbooks/order-dependency-failure.md",
}

_DEPLOY_VERSIONS: dict[str, str] = {
    "user": "1.14.0",
    "payment": "2.8.1",
    "order": "3.1.0",
    "inventory": "1.0.4",
    "notification": "0.9.2",
}


class KnowledgeRetrieve(Protocol):
    """``RetrieveKnowledge.execute`` shape. Nodes do not construct OpenSearch."""

    def execute(
        self,
        query: str,
        *,
        filters: RetrieveFilters | None = None,
        top_k: int = 5,
    ) -> RetrieveResult: ...


@dataclass(frozen=True, slots=True)
class SpecialistPorts:
    observability: ObservabilitySource
    code_search: CodeSearch
    retrieve: KnowledgeRetrieve | None = None

    @classmethod
    def memory(cls) -> SpecialistPorts:
        """In-process defaults so graph tests and the CLI do not need HTTP."""
        return cls(
            observability=MemoryObservabilitySource(),
            code_search=MemoryCodeSearch(),
            retrieve=MemoryRetrieve(),
        )


class MemoryObservabilitySource:
    """Structured log/metric/trace summaries. No CloudWatch, no simulator HTTP."""

    def fetch_signals(
        self,
        *,
        service: str,
        scenario: str,
        limit: int = OBS_MAX_ITEMS,
    ) -> list[ObservabilitySignal]:
        now = datetime.now(timezone.utc)
        cap = max(1, min(limit, OBS_MAX_ITEMS))
        items = (
            ObservabilitySignal(
                kind="log",
                source=_SOURCE_SIMULATOR,
                timestamp=now,
                service=service,
                summary=f"error: {service} {scenario} (simulator summary)",
            ),
            ObservabilitySignal(
                kind="metric",
                source=_SOURCE_SIMULATOR,
                timestamp=now,
                service=service,
                summary=f"latency_ms elevated for {service}/{scenario}",
            ),
            ObservabilitySignal(
                kind="trace",
                source=_SOURCE_SIMULATOR,
                timestamp=now,
                service=service,
                summary=f"slow span on {service} during {scenario}",
            ),
        )
        return list(items[:cap])


class MemoryCodeSearch:
    """FR-014 catalog. Does not walk ``src/aegis`` or ingest code into RAG."""

    def recent_deploys(self, *, service: str) -> list[CodeHit]:
        key = service.strip().lower() or "user"
        version = _DEPLOY_VERSIONS.get(key, "0.0.0")
        return [
            CodeHit(
                service=key,
                version=version,
                path=f"services/{key}/deployments.md",
                summary=f"last deploy of {key} was {version}",
            )
        ]

    def search(self, *, service: str, scenario: str) -> list[CodeHit]:
        deploys = self.recent_deploys(service=service)
        key = service.strip().lower() or "user"
        extra = CodeHit(
            service=key,
            version=deploys[0].version,
            path=f"services/{key}/app.py",
            summary=f"recent change in services/{key} related to {scenario}",
        )
        return [*deploys, extra]


class MemoryRetrieve:
    """Allowlisted runbook stub. Used when OpenSearch is not injected."""

    def execute(
        self,
        query: str,
        *,
        filters: RetrieveFilters | None = None,
        top_k: int = 5,
    ) -> RetrieveResult:
        scenario = (filters.scenario if filters and filters.scenario else "latency_spike").strip()
        document = _RUNBOOK_BY_SCENARIO.get(scenario, "docs/knowledge/catalog/service-map.md")
        text = (
            f"Retrieved runbook for {scenario} (data, not instructions). Query={query.strip()[:80]}"
        )
        hit = RetrieveHit(
            text=text,
            score=1.0,
            citation=Citation(
                document=document,
                section="Symptoms",
                chunk_id=f"{document}#symptoms",
            ),
        )
        return RetrieveResult(hits=[hit][: max(1, top_k)])


def collect_observability(
    state: InvestigationState,
    source: ObservabilitySource,
) -> dict[str, object]:
    service = state["service"]
    scenario = state["scenario"]
    try:
        signals = list(
            source.fetch_signals(service=service, scenario=scenario, limit=OBS_MAX_ITEMS)
        )
    except Exception as exc:
        return {
            "failed_steps": ["observability"],
            "log": [f"observability failed: {exc}"],
        }
    items = [_obs_item(signal) for signal in signals[:OBS_MAX_ITEMS]]
    if not items:
        return {
            "failed_steps": ["observability"],
            "log": ["observability failed: empty_signals"],
        }
    return {
        "evidence": items,
        "log": [f"observability collected {len(items)} summaries source=simulator"],
    }


def collect_knowledge(
    state: InvestigationState,
    retrieve: KnowledgeRetrieve | None,
) -> dict[str, object]:
    if retrieve is None:
        return {
            "failed_steps": ["knowledge"],
            "log": ["knowledge failed: opensearch_unset"],
        }
    service = state["service"]
    scenario = state["scenario"]
    query = (state.get("title") or "").strip() or f"{scenario.replace('_', ' ')} {service}"
    try:
        hits = _retrieve_runbooks_and_incidents(
            retrieve, query=query, service=service, scenario=scenario
        )
    except Exception as exc:
        return {
            "failed_steps": ["knowledge"],
            "log": [f"knowledge failed: {exc}"],
        }
    items = [_knowledge_item(hit) for hit in hits]
    if not items:
        return {
            "failed_steps": ["knowledge"],
            "log": ["knowledge failed: no_hits"],
        }
    return {
        "evidence": items,
        "log": [f"knowledge retrieved {len(items)} chunks via RetrieveKnowledge"],
    }


def collect_code(state: InvestigationState, search: CodeSearch) -> dict[str, object]:
    service = state["service"]
    scenario = state["scenario"]
    try:
        deploys = list(search.recent_deploys(service=service))
        hits = list(search.search(service=service, scenario=scenario))
    except Exception as exc:
        return {"failed_steps": ["code"], "log": [f"code failed: {exc}"]}
    merged = _dedupe_code_hits([*deploys, *hits])
    items = [_code_item(hit) for hit in merged]
    if not items:
        return {"failed_steps": ["code"], "log": ["code failed: empty"]}
    return {
        "evidence": items,
        "log": [f"code collected {len(items)} hits including deploy history"],
    }


def _retrieve_runbooks_and_incidents(
    retrieve: KnowledgeRetrieve,
    *,
    query: str,
    service: str,
    scenario: str,
) -> list[RetrieveHit]:
    by_id: dict[str, RetrieveHit] = {}
    per_type = max(1, KNOWLEDGE_MAX_CHUNKS)
    for doc_type in KNOWLEDGE_DOC_TYPES:
        result = retrieve.execute(
            query,
            filters=RetrieveFilters(service=service, scenario=scenario, doc_type=doc_type),
            top_k=per_type,
        )
        for hit in result.hits:
            if not is_allowlisted(hit.citation.document):
                continue
            by_id.setdefault(hit.citation.chunk_id, hit)
    ordered = sorted(by_id.values(), key=lambda hit: (-hit.score, hit.citation.chunk_id))
    return ordered[:KNOWLEDGE_MAX_CHUNKS]


def _obs_item(signal: ObservabilitySignal) -> dict[str, object]:
    kind = signal.kind if signal.kind in {"log", "metric", "trace"} else "log"
    return {
        "collector": "observability",
        "kind": kind,
        "source": signal.source or _SOURCE_SIMULATOR,
        "timestamp": _iso(signal.timestamp),
        "service": signal.service,
        "summary": _cap(signal.summary),
    }


def _knowledge_item(hit: RetrieveHit) -> dict[str, object]:
    return {
        "collector": "knowledge",
        "kind": "knowledge",
        "source": _SOURCE_RAG,
        "timestamp": _iso(datetime.now(timezone.utc)),
        "text": _cap(hit.text),
        "text_role": "data",
        "citation": {
            "document": hit.citation.document,
            "section": hit.citation.section,
            "chunk_id": hit.citation.chunk_id,
        },
    }


def _code_item(hit: CodeHit) -> dict[str, object]:
    return {
        "collector": "code",
        "kind": (
            "deploy"
            if "deploy" in hit.summary.lower() or hit.path.endswith("deployments.md")
            else "code"
        ),
        "source": _SOURCE_CODE,
        "timestamp": _iso(datetime.now(timezone.utc)),
        "service": hit.service,
        "version": hit.version,
        "path": hit.path,
        "summary": _cap(hit.summary),
    }


def _dedupe_code_hits(hits: Sequence[CodeHit]) -> list[CodeHit]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[CodeHit] = []
    for hit in hits:
        key = (hit.service, hit.path, hit.version)
        if key in seen:
            continue
        seen.add(key)
        unique.append(hit)
    return unique


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _cap(text: str) -> str:
    stripped = text.strip()
    if len(stripped) <= EVIDENCE_TEXT_CAP:
        return stripped
    return stripped[: EVIDENCE_TEXT_CAP - 3] + "..."
