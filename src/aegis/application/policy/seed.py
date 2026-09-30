"""In-process default rules matching the Alembic seed (4.5 / 5.4 read tools)."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import UUID

from aegis.domain.gateway.enums import ActionClass
from aegis.domain.policy.entity import WILDCARD, PolicyRule

SEED_ACTOR = "system:seed"

SEED_RETRIEVE_KNOWLEDGE_ID = UUID("a1111111-0000-4000-8000-000000000001")
SEED_FETCH_SIGNALS_ID = UUID("a1111111-0000-4000-8000-000000000002")
SEED_SEARCH_CODE_ID = UUID("a1111111-0000-4000-8000-000000000003")
SEED_LIST_DEPLOYS_ID = UUID("a1111111-0000-4000-8000-000000000004")

_SEED_AT = datetime(2026, 9, 28, 0, 0, tzinfo=timezone.utc)


def seed_read_rules() -> tuple[PolicyRule, ...]:
    """Allow the three specialist read tools plus ``list_deploys`` (code node)."""
    return (
        PolicyRule.create(
            rule_id=SEED_RETRIEVE_KNOWLEDGE_ID,
            tool_name="retrieve_knowledge",
            action_class=ActionClass.READ,
            scope=WILDCARD,
            allowed=True,
            reason="seed: knowledge retrieve",
            actor=SEED_ACTOR,
            created_at=_SEED_AT,
        ),
        PolicyRule.create(
            rule_id=SEED_FETCH_SIGNALS_ID,
            tool_name="fetch_signals",
            action_class=ActionClass.READ,
            scope=WILDCARD,
            allowed=True,
            reason="seed: observability signals",
            actor=SEED_ACTOR,
            created_at=_SEED_AT,
        ),
        PolicyRule.create(
            rule_id=SEED_SEARCH_CODE_ID,
            tool_name="search_code",
            action_class=ActionClass.READ,
            scope=WILDCARD,
            allowed=True,
            reason="seed: code search",
            actor=SEED_ACTOR,
            created_at=_SEED_AT,
        ),
        PolicyRule.create(
            rule_id=SEED_LIST_DEPLOYS_ID,
            tool_name="list_deploys",
            action_class=ActionClass.READ,
            scope=WILDCARD,
            allowed=True,
            reason="seed: code deploys",
            actor=SEED_ACTOR,
            created_at=_SEED_AT,
        ),
    )
