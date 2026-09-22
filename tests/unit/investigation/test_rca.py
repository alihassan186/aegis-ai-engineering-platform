"""RCA schema, grounding, redaction, and low-confidence escalate (FR-030–033)."""

from __future__ import annotations

from uuid import UUID, uuid4

import pytest

from aegis.application.investigation.rca import (
    CONFIDENCE_THRESHOLD,
    EvidencePackItem,
    assemble_rca_prompt,
    extract_pack_ids,
    generate_rca,
    parse_rca_output,
)
from aegis.domain.investigation import EscalateReason
from aegis.infrastructure.llm.fake_llm import FakeLlm
from aegis.shared.exceptions import ValidationError

_AWS_DUMMY = "AKIAIOSFODNN7EXAMPLE"


def _pack(*ids: UUID) -> list[EvidencePackItem]:
    return [
        EvidencePackItem(
            evidence_id=item,
            source="simulator",
            excerpt="p99 latency 1.8s on payment checkout",
            citation={},
        )
        for item in ids
    ]


def test_extract_pack_ids_ignores_incident_uuid() -> None:
    incident = uuid4()
    first, second = uuid4(), uuid4()
    user = (
        f"DATA\nincident_id: {incident}\nevidence:\n"
        f"- id: {first}\n- id: {second}\n"
    )
    assert extract_pack_ids(user) == [first, second]


def test_fake_llm_schema_validates_and_cites_pack_ids() -> None:
    first, second = uuid4(), uuid4()
    generation = generate_rca(
        incident_id=str(uuid4()),
        service="payment",
        scenario="latency_spike",
        pack=_pack(first, second),
        llm=FakeLlm(),
    )

    assert generation.outcome == "pending_review"
    assert generation.report is not None
    assert generation.report.review_status.value == "pending_review"
    cited = {item.evidence_id for item in generation.report.citations}
    assert cited <= {first, second}
    assert cited
    assert generation.payload is not None
    assert str(generation.report.incident_id) not in {str(item) for item in cited}
    assert generation.payload["status"] in {"hypothesis", "confirmed"}
    assert "root_cause" in generation.payload
    assert generation.payload["evidence_citations"]


def test_missing_citation_retries_then_escalates() -> None:
    allowed = uuid4()
    invented = uuid4()
    bad = {
        "summary": "invented cause",
        "root_cause": "not in the pack",
        "contributing_factors": ["guess"],
        "confidence": 0.9,
        "status": "confirmed",
        "evidence_citations": [
            {
                "evidence_id": str(invented),
                "source": "simulator",
                "relevance": "hallucinated",
            }
        ],
        "recommended_actions": ["do nothing"],
    }
    llm = FakeLlm(responses=[bad, bad])

    generation = generate_rca(
        incident_id=str(uuid4()),
        service="payment",
        scenario="latency_spike",
        pack=_pack(allowed),
        llm=llm,
    )

    assert llm.calls == 2
    assert generation.outcome == "escalated"
    assert generation.escalate_reason is EscalateReason.AGENT_FAILURE
    assert generation.report is None


def test_ungrounded_id_is_rejected_by_parser() -> None:
    allowed = uuid4()
    with pytest.raises(ValidationError, match="not in the pack"):
        parse_rca_output(
            {
                "summary": "x",
                "root_cause": "y",
                "contributing_factors": [],
                "confidence": 0.7,
                "status": "hypothesis",
                "evidence_citations": [
                    {
                        "evidence_id": str(uuid4()),
                        "source": "simulator",
                        "relevance": "nope",
                    }
                ],
                "recommended_actions": [],
            },
            allowed_ids=frozenset({allowed}),
        )


def test_redacted_secret_does_not_appear_in_prompt() -> None:
    item = EvidencePackItem(
        evidence_id=uuid4(),
        source="simulator",
        excerpt=f"auth failed key={_AWS_DUMMY}",
        citation={},
    )
    prompt = assemble_rca_prompt(
        incident_id=str(uuid4()),
        service="payment",
        scenario="latency_spike",
        pack=[item],
    )

    assert _AWS_DUMMY not in prompt.user
    assert _AWS_DUMMY not in prompt.system
    assert "[REDACTED:aws_access_key]" in prompt.user
    assert "DATA" in prompt.user
    assert prompt.input_tokens > 0


def test_low_confidence_escalates_and_stays_hypothesis() -> None:
    evidence_id = uuid4()
    low = {
        "summary": "weak signal",
        "root_cause": "unclear",
        "contributing_factors": [],
        "confidence": CONFIDENCE_THRESHOLD - 0.2,
        "status": "confirmed",
        "evidence_citations": [
            {
                "evidence_id": str(evidence_id),
                "source": "simulator",
                "relevance": "thin",
            }
        ],
        "recommended_actions": ["page the on-call"],
    }
    generation = generate_rca(
        incident_id=str(uuid4()),
        service="payment",
        scenario="latency_spike",
        pack=_pack(evidence_id),
        llm=FakeLlm(responses=[low]),
    )

    assert generation.outcome == "escalated"
    assert generation.escalate_reason is EscalateReason.LOW_CONFIDENCE
    assert generation.report is not None
    assert generation.report.finding_status.value == "hypothesis"
    assert generation.report.review_status.value == "pending_review"
