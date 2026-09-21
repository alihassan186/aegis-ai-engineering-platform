"""Evidence source and kind (FR-017). Not a dump of raw telemetry."""

from enum import StrEnum


class EvidenceSource(StrEnum):
    """Where the item came from. ``manual`` is reserved for FR-024 (Step 4.9)."""

    SIMULATOR = "simulator"
    RETRIEVE = "retrieve"
    CODE = "code"
    MANUAL = "manual"


class EvidenceKind(StrEnum):
    """What the excerpt represents. Vectors stay in OpenSearch, not here."""

    LOG = "log"
    METRIC = "metric"
    TRACE = "trace"
    CHUNK = "chunk"
    DEPLOY = "deploy"
    NOTE = "note"
