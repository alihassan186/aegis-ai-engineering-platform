"""Investigation escalation vocabulary (FR-025, FR-026).

These values are the product language for *why* the commander stopped.
Step 4.9 will expose them on the progress API; 4.10 will notify on them.
``low_confidence`` and ``agent_failure`` are reserved until 4.8 / 4.5
produce those signals. Routing must not invent parallel strings.
"""

from enum import StrEnum


class EscalateReason(StrEnum):
    """First-class escalate outcomes — not exceptions."""

    MAX_HOPS = "max_hops"
    MAX_DURATION = "max_duration"
    LOW_CONFIDENCE = "low_confidence"
    AGENT_FAILURE = "agent_failure"
    # v0.5 first-hop policy for FR-083 dependency_failure (human owns vendor/outage).
    DEPENDENCY_FAILURE = "dependency_failure"
