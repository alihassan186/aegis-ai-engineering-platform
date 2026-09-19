"""Compose specialist ports for the investigation worker (Step 4.5)."""

from __future__ import annotations

from aegis.application.investigation.collect import SpecialistPorts
from aegis.application.rag.retrieve import RetrieveKnowledge
from aegis.config.settings import Settings
from aegis.infrastructure.code.fake_code_search import FakeCodeSearch
from aegis.infrastructure.observability.simulator_client import SimulatorObservabilityClient
from aegis.infrastructure.rag.embedder import build_embedder
from aegis.infrastructure.rag.opensearch_client import OpenSearchKnowledgeStore


def build_specialist_ports(settings: Settings) -> SpecialistPorts:
    """HTTP simulator + fake code search + retrieve when OpenSearch is configured."""
    retrieve = None
    if settings.opensearch_url:
        retrieve = RetrieveKnowledge(
            embedder=build_embedder(settings),
            store=OpenSearchKnowledgeStore(settings.opensearch_url),
        )
    return SpecialistPorts(
        observability=SimulatorObservabilityClient(settings.simulator_base_url),
        code_search=FakeCodeSearch(),
        retrieve=retrieve,
    )
