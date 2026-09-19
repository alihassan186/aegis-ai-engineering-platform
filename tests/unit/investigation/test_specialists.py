"""Specialist agents collect structured evidence through ports (Step 4.5)."""

from __future__ import annotations

import inspect
from collections.abc import Mapping, Sequence
from datetime import datetime, timezone

from aegis.application.investigation.collect import (
    MemoryObservabilitySource,
    SpecialistPorts,
    collect_code,
    collect_knowledge,
    collect_observability,
)
from aegis.application.investigation.nodes import knowledge_node
from aegis.application.investigation.plan import next_action
from aegis.application.rag.allowlist import ALLOWED_RELATIVE_PATHS
from aegis.application.rag.retrieve import (
    Citation,
    RetrieveFilters,
    RetrieveHit,
    RetrieveKnowledge,
    RetrieveResult,
)
from aegis.core.protocols import KnowledgeHit, ObservabilitySignal
from aegis.domain.investigation import EscalateReason
from aegis.infrastructure.code.fake_code_search import FakeCodeSearch
from aegis.infrastructure.rag.embedder import FakeEmbedder


def _state(service: str = "payment", scenario: str = "latency_spike") -> dict[str, object]:
    return {
        "incident_id": "INC-TEST",
        "service": service,
        "scenario": scenario,
        "hops": 1,
        "next_agent": "",
        "status": "running",
        "human_decision": "",
        "evidence": [],
        "log": [],
        "failed_steps": [],
    }


def test_observability_items_have_source_timestamp_and_kind() -> None:
    update = collect_observability(_state(), MemoryObservabilitySource())  # type: ignore[arg-type]

    items = update["evidence"]
    assert isinstance(items, list) and items
    assert len(items) <= 20
    kinds = {item["kind"] for item in items}
    assert kinds <= {"log", "metric", "trace"}
    assert kinds & {"log", "metric", "trace"}
    for item in items:
        assert item["collector"] == "observability"
        assert item["source"] == "simulator"
        assert item["timestamp"]
        datetime.fromisoformat(str(item["timestamp"]).replace("Z", "+00:00"))


def test_observability_accepts_injected_fake_source() -> None:
    now = datetime(2026, 9, 18, 12, 0, tzinfo=timezone.utc)

    class _Fake:
        def fetch_signals(
            self, *, service: str, scenario: str, limit: int = 20
        ) -> list[ObservabilitySignal]:
            return [
                ObservabilitySignal(
                    kind="metric",
                    source="simulator",
                    timestamp=now,
                    service=service,
                    summary=f"{service} {scenario} p99",
                )
            ]

    update = collect_observability(_state(), _Fake())  # type: ignore[arg-type]
    item = update["evidence"][0]
    assert item["kind"] == "metric"
    assert item["source"] == "simulator"
    assert "2026-09-18" in str(item["timestamp"])


def test_knowledge_citations_are_allowlisted() -> None:
    path = "docs/knowledge/runbooks/payment-latency-spike.md"
    assert path in ALLOWED_RELATIVE_PATHS

    class _RecordingRetrieve:
        def __init__(self) -> None:
            self.calls: list[tuple[str, RetrieveFilters | None, int]] = []

        def execute(
            self,
            query: str,
            *,
            filters: RetrieveFilters | None = None,
            top_k: int = 5,
        ) -> RetrieveResult:
            self.calls.append((query, filters, top_k))
            return RetrieveResult(
                hits=[
                    RetrieveHit(
                        text="Payment latency runbook body (data).",
                        score=0.9,
                        citation=Citation(
                            document=path,
                            section="Symptoms",
                            chunk_id=f"{path}#symptoms",
                        ),
                    )
                ]
            )

    retrieve = _RecordingRetrieve()
    update = collect_knowledge(_state(), retrieve)  # type: ignore[arg-type]
    documents = [item["citation"]["document"] for item in update["evidence"]]
    assert documents
    assert all(
        doc.startswith("docs/knowledge/") or doc.startswith("docs/adr/") for doc in documents
    )
    assert path in documents
    assert all(item["text_role"] == "data" for item in update["evidence"])
    assert retrieve.calls
    doc_types = {call[1].doc_type for call in retrieve.calls if call[1] is not None}
    assert doc_types <= {"runbook", "incident_report"}
    assert "runbook" in doc_types
    assert all(
        call[1] is not None and call[1].scenario == "latency_spike" for call in retrieve.calls
    )
    assert all(call[1] is not None and call[1].service == "payment" for call in retrieve.calls)


def test_knowledge_uses_retrieve_knowledge_with_fake_store() -> None:
    path = "docs/knowledge/runbooks/payment-latency-spike.md"
    hit = KnowledgeHit(
        chunk_id=f"{path}#symptoms",
        text="Payment p99 latency runbook (data).",
        source_path=path,
        section="Symptoms",
        score=1.0,
    )
    store = _MemorySearchStore([hit])
    retrieve = RetrieveKnowledge(embedder=FakeEmbedder(), store=store)
    node = knowledge_node(retrieve)
    update = node(_state())  # type: ignore[arg-type]
    citation = update["evidence"][0]["citation"]
    assert citation["document"] == path
    assert citation["section"] == "Symptoms"
    assert citation["chunk_id"].startswith(path)
    assert store.filters
    assert {row.get("doc_type") for row in store.filters} <= {"runbook", "incident_report"}


def test_knowledge_unset_retrieve_records_failed_step_without_raising() -> None:
    update = collect_knowledge(_state(), None)  # type: ignore[arg-type]
    assert update["failed_steps"] == ["knowledge"]
    assert "opensearch_unset" in str(update["log"])
    assert "evidence" not in update


def test_failed_knowledge_escalates_agent_failure() -> None:
    decision = next_action(
        scenario="unspecified",
        hops=1,
        evidence=(),
        failed_steps=["knowledge"],
    )
    assert decision.escalate_reason is EscalateReason.AGENT_FAILURE


def test_code_fake_mentions_version_and_does_not_walk_src() -> None:
    search = FakeCodeSearch()
    source = inspect.getsource(FakeCodeSearch)
    assert "src/aegis" not in source
    assert "rglob" not in source
    assert "os.walk" not in source
    assert "Path(" not in source

    update = collect_code(_state("user", "bad_deployment"), search)  # type: ignore[arg-type]
    assert any("1.14.0" in str(item.get("version")) for item in update["evidence"])
    assert any("1.14.0" in str(item.get("summary")) for item in update["evidence"])
    assert all(not str(item.get("path", "")).startswith("src/aegis") for item in update["evidence"])


def test_memory_ports_match_graph_defaults() -> None:
    ports = SpecialistPorts.memory()
    obs = collect_observability(_state(), ports.observability)  # type: ignore[arg-type]
    code = collect_code(_state("user", "bad_deployment"), ports.code_search)  # type: ignore[arg-type]
    kb = collect_knowledge(_state(), ports.retrieve)  # type: ignore[arg-type]
    assert obs["evidence"]
    assert any("1.14.0" in str(item.get("version")) for item in code["evidence"])
    assert kb["evidence"][0]["citation"]["document"] in ALLOWED_RELATIVE_PATHS


class _MemorySearchStore:
    def __init__(self, hits: list[KnowledgeHit]) -> None:
        self.hits = hits
        self.filters: list[Mapping[str, str]] = []

    def ensure_hybrid_index(self) -> None:
        return None

    def bulk_upsert(self, documents: Sequence[Mapping[str, object]]) -> int:
        return 0

    def count(self) -> int:
        return len(self.hits)

    def delete_by_source_path(self, source_path: str) -> int:
        return 0

    def search_match(
        self,
        *,
        text: str,
        source_path: str | None = None,
        size: int = 5,
    ) -> list[dict[str, object]]:
        return []

    def search_text(
        self,
        *,
        query: str,
        filters: Mapping[str, str],
        size: int,
    ) -> list[KnowledgeHit]:
        self.filters.append(dict(filters))
        return self.hits[:size]

    def search_knn(
        self,
        *,
        embedding: Sequence[float],
        filters: Mapping[str, str],
        size: int,
    ) -> list[KnowledgeHit]:
        self.filters.append(dict(filters))
        return self.hits[:size]
