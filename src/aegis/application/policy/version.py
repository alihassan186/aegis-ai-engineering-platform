"""Version of the active rule set (Step 5.11, FR-066 / FR-062).

``policy_version`` answers the auditor question "which policy allowed this?".
It is a content hash of the active rules, so any create / edit / delete changes
it, including a delete that no per-rule counter could see. Same rules in two
processes produce the same string. Timestamps are excluded on purpose.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Iterable

from aegis.domain.policy.entity import PolicyRule

POLICY_VERSION_PREFIX = "pv1-"
_DIGEST_CHARS = 12


def policy_version_for(rules: Iterable[PolicyRule]) -> str:
    """Stable ``pv1-<12 hex>`` for a rule set. Order of ``rules`` does not matter."""
    rows = sorted(
        (
            str(rule.id),
            rule.tool_name,
            rule.action_class.value,
            rule.scope,
            bool(rule.allowed),
            int(rule.version),
        )
        for rule in rules
    )
    blob = json.dumps(rows, separators=(",", ":"))
    digest = hashlib.sha256(blob.encode("utf-8")).hexdigest()
    return f"{POLICY_VERSION_PREFIX}{digest[:_DIGEST_CHARS]}"
