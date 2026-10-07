"""Compose specialist ports for the investigation worker (Step 4.5)."""

from __future__ import annotations

from aegis.application.gateway.limits import validate_http_target
from aegis.application.investigation.collect import SpecialistPorts
from aegis.application.rag.retrieve import RetrieveKnowledge
from aegis.config.settings import Settings
from aegis.infrastructure.code.fake_code_search import FakeCodeSearch
from aegis.infrastructure.llm import build_llm
from aegis.infrastructure.observability.simulator_client import SimulatorObservabilityClient
from aegis.infrastructure.rag.embedder import build_embedder
from aegis.infrastructure.rag.opensearch_client import OpenSearchKnowledgeStore


def build_specialist_ports(settings: Settings) -> SpecialistPorts:
    """HTTP simulator + fake code search + retrieve when OpenSearch is configured.

    Base URLs come from settings only (never from a tool parameter) and must pass the
    host allowlist before any adapter is built. A bad URL stops the worker (fail closed).
    """
    simulator_url = validate_http_target(
        settings.simulator_base_url, allowed_hosts=settings.tool_allowed_hosts
    )
    retrieve = None
    if settings.opensearch_url:
        opensearch_url = validate_http_target(
            settings.opensearch_url, allowed_hosts=settings.tool_allowed_hosts
        )
        retrieve = RetrieveKnowledge(
            embedder=build_embedder(settings),
            store=OpenSearchKnowledgeStore(opensearch_url),
        )
    return SpecialistPorts(
        observability=SimulatorObservabilityClient(simulator_url),
        code_search=FakeCodeSearch(),
        retrieve=retrieve,
        llm=build_llm(settings),
    )
