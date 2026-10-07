"""Specialist adapters: ports in, structured evidence out. No HTTP, no OpenSearch.

Tool calls go through ``InvokeTool`` (Step 5.1). Ports are runners, not a bypass.
"""

from __future__ import annotations

import logging
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Protocol

from aegis.application.evidence.record_evidence import (
    EvidenceRecorder,
    incident_id_from_state,
)
from aegis.application.gateway.invoke_tool import InvokeTool
from aegis.application.investigation.state import (
    EVIDENCE_TEXT_CAP,
    OBS_MAX_ITEMS,
    InvestigationState,
)
from aegis.application.rag.retrieve import (
    Citation,
    RetrieveFilters,
    RetrieveHit,
    RetrieveResult,
)
from aegis.application.security.redact import redact
from aegis.core.protocols import (
    CodeHit,
    CodeSearch,
    LlmClient,
    ObservabilitySignal,
    ObservabilitySource,
)
from aegis.domain.auth.agent_identity import AgentIdentity
from aegis.domain.gateway.decision import GatewayDecision
from aegis.domain.gateway.request import ToolInvokeRequest
from aegis.tools.fetch_signals import make_fetch_signals
from aegis.tools.list_deploys import make_list_deploys
from aegis.tools.retrieve_knowledge import make_retrieve_knowledge
from aegis.tools.search_code import make_search_code

logger = logging.getLogger(__name__)

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
    recorder: EvidenceRecorder | None = None
    llm: LlmClient | None = None
    gateway: InvokeTool | None = None

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
    recorder: EvidenceRecorder | None = None,
    *,
    gateway: InvokeTool | None = None,
) -> dict[str, object]:
    service = state["service"]
    scenario = state["scenario"]
    invoke = gateway or InvokeTool(tools={"fetch_signals": make_fetch_signals(source)})
    try:
        decision = invoke.invoke(
            ToolInvokeRequest(
                agent_id=_agent_id(invoke, AgentIdentity.OBSERVABILITY),
                tool_name="fetch_signals",
                parameters={
                    "service": service,
                    "scenario": scenario,
                    "limit": OBS_MAX_ITEMS,
                },
                incident_id=str(state.get("incident_id") or "unknown"),
            )
        )
    except Exception as exc:
        return {
            "failed_steps": ["observability"],
            "log": [f"observability failed: {exc}"],
        }
    if not decision.allowed:
        return {
            "failed_steps": ["observability"],
            "log": [f"observability denied: {decision.reason}"],
        }
    signals = list(decision.result or [])
    items = _tag_untrusted(
        [_obs_item(signal) for signal in signals[:OBS_MAX_ITEMS]],
        decision,
    )
    if not items:
        return {
            "failed_steps": ["observability"],
            "log": ["observability failed: empty_signals"],
        }
    _record_collected(state, items, recorder)
    return {
        "evidence": items,
        "log": [f"observability collected {len(items)} summaries source=simulator"],
    }


def collect_knowledge(
    state: InvestigationState,
    retrieve: KnowledgeRetrieve | None,
    recorder: EvidenceRecorder | None = None,
    *,
    gateway: InvokeTool | None = None,
) -> dict[str, object]:
    if retrieve is None and gateway is None:
        return {
            "failed_steps": ["knowledge"],
            "log": ["knowledge failed: opensearch_unset"],
        }
    service = state["service"]
    scenario = state["scenario"]
    query = (state.get("title") or "").strip() or f"{scenario.replace('_', ' ')} {service}"
    invoke = gateway or InvokeTool(
        tools={"retrieve_knowledge": make_retrieve_knowledge(retrieve)}
        if retrieve is not None
        else {}
    )
    try:
        decision = invoke.invoke(
            ToolInvokeRequest(
                agent_id=_agent_id(invoke, AgentIdentity.KNOWLEDGE),
                tool_name="retrieve_knowledge",
                parameters={"query": query, "service": service, "scenario": scenario},
                incident_id=str(state.get("incident_id") or "unknown"),
            )
        )
    except Exception as exc:
        return {
            "failed_steps": ["knowledge"],
            "log": [f"knowledge failed: {exc}"],
        }
    if not decision.allowed:
        reason = decision.reason
        if reason == "denied:not_registered":
            reason = "opensearch_unset"
        return {
            "failed_steps": ["knowledge"],
            "log": [f"knowledge denied: {reason}"],
        }
    hits = list(decision.result or [])
    items = _tag_untrusted([_knowledge_item(hit) for hit in hits], decision)
    if not items:
        return {
            "failed_steps": ["knowledge"],
            "log": ["knowledge failed: no_hits"],
        }
    _record_collected(state, items, recorder)
    return {
        "evidence": items,
        "log": [f"knowledge retrieved {len(items)} chunks via RetrieveKnowledge"],
    }


def collect_code(
    state: InvestigationState,
    search: CodeSearch,
    recorder: EvidenceRecorder | None = None,
    *,
    gateway: InvokeTool | None = None,
) -> dict[str, object]:
    service = state["service"]
    scenario = state["scenario"]
    invoke = gateway or InvokeTool(
        tools={
            "list_deploys": make_list_deploys(search),
            "search_code": make_search_code(search),
        }
    )
    incident_id = str(state.get("incident_id") or "unknown")
    agent_id = _agent_id(invoke, AgentIdentity.CODE)
    try:
        deploys_decision = invoke.invoke(
            ToolInvokeRequest(
                agent_id=agent_id,
                tool_name="list_deploys",
                parameters={"service": service},
                incident_id=incident_id,
            )
        )
        hits_decision = invoke.invoke(
            ToolInvokeRequest(
                agent_id=agent_id,
                tool_name="search_code",
                parameters={"service": service, "scenario": scenario},
                incident_id=incident_id,
            )
        )
    except Exception as exc:
        return {"failed_steps": ["code"], "log": [f"code failed: {exc}"]}
    if not deploys_decision.allowed or not hits_decision.allowed:
        reason = deploys_decision.reason if not deploys_decision.allowed else hits_decision.reason
        return {"failed_steps": ["code"], "log": [f"code denied: {reason}"]}
    deploys = list(deploys_decision.result or [])
    hits = list(hits_decision.result or [])
    merged = _dedupe_code_hits([*deploys, *hits])
    items = _tag_untrusted([_code_item(hit) for hit in merged], hits_decision)
    if not items:
        return {"failed_steps": ["code"], "log": ["code failed: empty"]}
    _record_collected(state, items, recorder)
    return {
        "evidence": items,
        "log": [f"code collected {len(items)} hits including deploy history"],
    }


def _tag_untrusted(
    items: list[dict[str, object]],
    decision: GatewayDecision,
) -> list[dict[str, object]]:
    """Step 5.9: evidence is tagged data from an audited call, not a raw port dump."""
    for item in items:
        item["untrusted"] = True
        item["tool"] = decision.tool_name
        item["audit_id"] = decision.audit_id
    return items


def _record_collected(
    state: InvestigationState,
    items: list[dict[str, object]],
    recorder: EvidenceRecorder | None,
) -> None:
    if recorder is None or not items:
        return
    incident_id = incident_id_from_state(state.get("incident_id"))
    if incident_id is None:
        return
    try:
        recorder.record_collected(incident_id, items)
    except Exception:
        logger.exception("evidence record failed; graph items still returned")


def _obs_item(signal: ObservabilitySignal | Mapping[str, object]) -> dict[str, object]:
    if isinstance(signal, Mapping):
        kind = str(signal.get("kind") or "log")
        if kind not in {"log", "metric", "trace"}:
            kind = "log"
        timestamp = signal.get("timestamp")
        return {
            "collector": "observability",
            "kind": kind,
            "source": str(signal.get("source") or _SOURCE_SIMULATOR),
            "timestamp": _as_iso(timestamp),
            "service": str(signal.get("service") or ""),
            "summary": _cap(str(signal.get("summary") or "")),
        }
    kind = signal.kind if signal.kind in {"log", "metric", "trace"} else "log"
    return {
        "collector": "observability",
        "kind": kind,
        "source": signal.source or _SOURCE_SIMULATOR,
        "timestamp": _iso(signal.timestamp),
        "service": signal.service,
        "summary": _cap(signal.summary),
    }


def _knowledge_item(hit: RetrieveHit | Mapping[str, object]) -> dict[str, object]:
    if isinstance(hit, Mapping):
        raw_citation = hit.get("citation")
        citation: Mapping[str, object] = raw_citation if isinstance(raw_citation, Mapping) else {}
        return {
            "collector": "knowledge",
            "kind": "knowledge",
            "source": _SOURCE_RAG,
            "timestamp": _iso(datetime.now(timezone.utc)),
            "text": _cap(str(hit.get("text") or "")),
            "text_role": "data",
            "citation": {
                "document": str(citation.get("document") or ""),
                "section": str(citation.get("section") or ""),
                "chunk_id": str(citation.get("chunk_id") or ""),
            },
        }
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


def _code_item(hit: CodeHit | Mapping[str, object]) -> dict[str, object]:
    if isinstance(hit, Mapping):
        summary = str(hit.get("summary") or "")
        path = str(hit.get("path") or "")
        is_deploy = "deploy" in summary.lower() or path.endswith("deployments.md")
        return {
            "collector": "code",
            "kind": "deploy" if is_deploy else "code",
            "source": _SOURCE_CODE,
            "timestamp": _iso(datetime.now(timezone.utc)),
            "service": str(hit.get("service") or ""),
            "version": str(hit.get("version") or ""),
            "path": path,
            "summary": _cap(summary),
        }
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


def _dedupe_code_hits(
    hits: Sequence[CodeHit | Mapping[str, object]],
) -> list[CodeHit | Mapping[str, object]]:
    seen: set[tuple[str, str, str]] = set()
    unique: list[CodeHit | Mapping[str, object]] = []
    for hit in hits:
        key = _code_key(hit)
        if key in seen:
            continue
        seen.add(key)
        unique.append(hit)
    return unique


def _code_key(hit: CodeHit | Mapping[str, object]) -> tuple[str, str, str]:
    if isinstance(hit, Mapping):
        return (
            str(hit.get("service") or ""),
            str(hit.get("path") or ""),
            str(hit.get("version") or ""),
        )
    return (hit.service, hit.path, hit.version)


def _agent_id(gateway: InvokeTool, default: AgentIdentity) -> str:
    """Use the node's bound identity when present; never a param-supplied id."""
    return gateway.bound_agent_id or default.value


def _as_iso(value: object) -> str:
    if isinstance(value, datetime):
        return _iso(value)
    if value is None:
        return _iso(datetime.now(timezone.utc))
    return str(value)


def _iso(value: datetime) -> str:
    if value.tzinfo is None:
        value = value.replace(tzinfo=timezone.utc)
    return value.astimezone(timezone.utc).isoformat()


def _cap(text: str) -> str:
    stripped = redact(text.strip()).text
    if len(stripped) <= EVIDENCE_TEXT_CAP:
        return stripped
    return stripped[: EVIDENCE_TEXT_CAP - 3] + "..."
