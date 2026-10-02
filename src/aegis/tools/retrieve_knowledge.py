"""``retrieve_knowledge`` — RetrieveKnowledge + allowlist, not a raw OpenSearch client."""

from __future__ import annotations

from collections.abc import Callable, Mapping
from typing import Any, Protocol

from pydantic import BaseModel, ConfigDict, Field

from aegis.application.rag.allowlist import is_allowlisted
from aegis.application.rag.retrieve import RetrieveFilters, RetrieveHit, RetrieveResult
from aegis.tools._limits import KNOWLEDGE_CAP
from aegis.tools._params import parse_params
from aegis.tools.timeout import run_with_timeout

ToolFn = Callable[[Mapping[str, Any]], Any]
KNOWLEDGE_DOC_TYPES = ("runbook", "incident_report")


class KnowledgeRetrieve(Protocol):
    def execute(
        self,
        query: str,
        *,
        filters: RetrieveFilters | None = None,
        top_k: int = 5,
    ) -> RetrieveResult: ...


class RetrieveKnowledgeParams(BaseModel):
    model_config = ConfigDict(extra="forbid")

    query: str = Field(default="", max_length=2000)
    service: str = Field(default="", max_length=255)
    scenario: str = Field(default="", max_length=128)


def make_retrieve_knowledge(retrieve: KnowledgeRetrieve) -> ToolFn:
    def run(params: Mapping[str, Any]) -> list[dict[str, Any]]:
        body = parse_params(RetrieveKnowledgeParams, params)

        def _call() -> list[dict[str, Any]]:
            hits = retrieve_runbooks_and_incidents(
                retrieve,
                query=body.query,
                service=body.service,
                scenario=body.scenario,
            )
            return [_hit_payload(hit) for hit in hits]

        return run_with_timeout(_call)

    return run


def retrieve_runbooks_and_incidents(
    retrieve: KnowledgeRetrieve,
    *,
    query: str,
    service: str,
    scenario: str,
) -> list[RetrieveHit]:
    by_id: dict[str, RetrieveHit] = {}
    per_type = max(1, KNOWLEDGE_CAP)
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
    return ordered[:KNOWLEDGE_CAP]


def _hit_payload(hit: RetrieveHit) -> dict[str, Any]:
    return {
        "text": hit.text,
        "score": hit.score,
        "citation": {
            "document": hit.citation.document,
            "section": hit.citation.section,
            "chunk_id": hit.citation.chunk_id,
        },
    }
