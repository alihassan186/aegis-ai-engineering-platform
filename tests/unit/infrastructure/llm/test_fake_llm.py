"""FakeLlm is deterministic and cites ids from the DATA block."""

from __future__ import annotations

from uuid import uuid4

from aegis.application.investigation.rca import fixture_rca_payload
from aegis.infrastructure.llm.fake_llm import FAKE_MODEL_ID, FakeLlm


def test_fake_llm_cites_ids_from_user_block() -> None:
    first, second = uuid4(), uuid4()
    user = f"DATA\n- id: {first}\n- id: {second}\n  excerpt: p99"
    result = FakeLlm().complete_json(system="role + schema", user=user)

    assert result.model_id == FAKE_MODEL_ID
    assert result.input_tokens > 0
    cited = {item["evidence_id"] for item in result.data["evidence_citations"]}
    assert cited <= {str(first), str(second)}
    assert cited
    assert result.data["status"] in {"hypothesis", "confirmed"}


def test_fixture_payload_matches_fake_llm() -> None:
    evidence_id = uuid4()
    user = f"DATA\n- id: {evidence_id}"
    assert FakeLlm().complete_json(system="s", user=user).data == fixture_rca_payload(user)
