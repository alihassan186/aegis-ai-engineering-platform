"""Named read-tool adapters behind the gateway (FR-060).

Application knows names. These modules talk to 4.5 ports only — no GitHub SDK,
no OpenSearch client. Simulator HTTP and FakeCodeSearch stay in infrastructure
and are injected by the worker.
"""

from aegis.tools.fetch_signals import make_fetch_signals
from aegis.tools.list_deploys import make_list_deploys
from aegis.tools.retrieve_knowledge import make_retrieve_knowledge
from aegis.tools.search_code import make_search_code

__all__ = [
    "make_fetch_signals",
    "make_list_deploys",
    "make_retrieve_knowledge",
    "make_search_code",
]
