"""
This module is responsible for creating a redacted Root Cause Analysis (RCA) prompt for an AI model (LLM),
and for validating the structured output that the LLM returns, in accordance with the requirements
outlined in features FR-030 to FR-033. The process involves assembling all necessary data and evidence
(including already-redacted evidence text), formatting it into a prompt compatible with the LLM's expected input,
sending it for inference (no direct boto3/aws SDK dependency; invocation is through the LlmClient protocol abstraction),
and finally validating that the returned object matches the expected JSON structure, including all required fields,
data types, and constraints. The module ensures incident and evidence privacy by using pre-redacted evidence text.
All domain redactions (for sensitive data) and prompt framework adaptations are done prior to passing content to the LLM.


No boto3. The LLM is a ``LlmClient``. Evidence text is labelled DATA and
already goes through ``redact_for_llm`` (FR-019 / NFR-034).
"""

from __future__ import annotations

import json
import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Any, Literal
from uuid import UUID, uuid5

from pydantic import BaseModel, Field
from pydantic import ValidationError as PydanticValidationError

from aegis.application.evidence.record_evidence import incident_id_from_state
from aegis.application.security.redact import redact_for_llm
from aegis.core.protocols import LlmClient, LlmJsonResult
from aegis.domain.investigation import EscalateReason
from aegis.domain.rca.entity import RcaCitation, RcaReport
from aegis.domain.rca.enums import RcaFindingStatus, RcaReviewStatus, RcaVersionKind
from aegis.shared.exceptions import ValidationError

CONFIDENCE_THRESHOLD = 0.6
MAX_PACK_ITEMS = 8
RCA_NAMESPACE = UUID("3c8b1f6e-4a71-4d2c-9e0b-7a5d2c1f0e48")
FAKE_MODEL_ID = "fake-llm"

_UUID_RE = re.compile(
    r"\b[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}\b"
)
_PACK_ID_RE = re.compile(
    r"(?im)^\s*- id:\s*("
    r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}"
    r")\b"
)


class RcaCitationSchema(BaseModel):
    evidence_id: UUID
    source: str = Field(min_length=1)
    relevance: str = Field(min_length=1)


class RcaOutputSchema(BaseModel):
    """Incident-flow Phase 3 RCA JSON (FR-030)."""

    summary: str = Field(min_length=1)
    root_cause: str = Field(min_length=1)
    contributing_factors: list[str]
    confidence: float = Field(ge=0.0, le=1.0)
    status: Literal["confirmed", "hypothesis"]
    evidence_citations: list[RcaCitationSchema]
    recommended_actions: list[str]


@dataclass(frozen=True, slots=True)
class EvidencePackItem:
    evidence_id: UUID
    source: str
    excerpt: str
    citation: Mapping[str, Any]


@dataclass(frozen=True, slots=True)
class RcaPrompt:
    system: str
    user: str
    pack_ids: frozenset[UUID]
    input_tokens: int


@dataclass(frozen=True, slots=True)
class RcaGeneration:
    outcome: str
    escalate_reason: EscalateReason | None
    report: RcaReport | None
    payload: dict[str, Any] | None
    attempts: int
    prompt: RcaPrompt


def estimate_tokens(text: str) -> int:
    """Cheap token stand-in (NFR-045 / NFR-070). ~4 characters per token."""
    stripped = text.strip()
    if not stripped:
        return 0
    return max(1, len(stripped) // 4)


def extract_pack_ids(text: str) -> list[UUID]:
    """Prefer ``- id:`` evidence lines so incident_id in DATA is not cited."""
    labeled = _PACK_ID_RE.findall(text)
    matches = labeled or [match.group(0) for match in _UUID_RE.finditer(text)]
    seen: set[UUID] = set()
    ordered: list[UUID] = []
    for raw in matches:
        value = UUID(raw)
        if value in seen:
            continue
        seen.add(value)
        ordered.append(value)
    return ordered


def pack_from_evidence_rows(rows: Sequence[Any]) -> list[EvidencePackItem]:
    items: list[EvidencePackItem] = []
    for row in rows[:MAX_PACK_ITEMS]:
        excerpt = redact_for_llm(str(getattr(row, "summary", "") or ""))
        meta = dict(getattr(row, "metadata", {}) or {})
        citation = meta.get("citation") if isinstance(meta.get("citation"), Mapping) else {}
        items.append(
            EvidencePackItem(
                evidence_id=row.id,
                source=str(getattr(row.source, "value", row.source)),
                excerpt=excerpt,
                citation=dict(citation),
            )
        )
    return items


def pack_from_graph_evidence(
    # The lone '*' in a function parameter list is used to indicate that all following parameters
    # must be specified as keyword arguments (not by position).
    # In this context, it enforces that the 'incident_key' and 'evidence' arguments
    # must be passed by name, which improves clarity and prevents mistakes when calling the function.
    *,
    incident_key: str,
    evidence: Sequence[object],
) -> list[EvidencePackItem]:
    items: list[EvidencePackItem] = []
    for index, raw in enumerate[object](evidence):
        if len(items) >= MAX_PACK_ITEMS:
            break
        if not isinstance(raw, Mapping):
            continue
        excerpt = redact_for_llm(str(raw.get("summary") or raw.get("text") or ""))
        source = str(raw.get("source") or raw.get("collector") or "unknown")
        raw_id = raw.get("id")
        try:
            if raw_id:
                evidence_id = UUID(str(raw_id))
            else:
                evidence_id = uuid5(
                    RCA_NAMESPACE, f"{incident_key}:{index}:{excerpt[:80]}"
                )
        except (ValueError, TypeError):
            evidence_id = uuid5(
                RCA_NAMESPACE, f"{incident_key}:{index}:{excerpt[:80]}"
            )
        citation = raw.get("citation") if isinstance(raw.get("citation"), Mapping) else {}
        items.append(
            EvidencePackItem(
                evidence_id=evidence_id,
                source=source,
                excerpt=excerpt,
                citation=dict(citation),
            )
        )
    return items


def assemble_rca_prompt(
    *,
    incident_id: str,
    service: str,
    scenario: str,
    pack: Sequence[EvidencePackItem],
) -> RcaPrompt:
    if not pack:
        raise ValidationError("RCA requires at least one evidence item in the pack.")
    schema_text = json.dumps(RcaOutputSchema.model_json_schema(), indent=2)
    system = (
        "You are the AEGIS RCA agent. Return one JSON object only.\n"
        "Use only the evidence in the DATA block. Do not invent evidence_id values.\n"
        "Recommended actions are text suggestions, not tools to execute.\n"
        "If evidence is incomplete, set status to hypothesis and lower confidence.\n"
        f"JSON schema:\n{schema_text}"
    )
    lines = [
        "DATA",
        f"incident_id: {incident_id}",
        f"service: {service}",
        f"scenario: {scenario}",
        "evidence:",
    ]
    for item in pack:
        lines.append(f"- id: {item.evidence_id}")
        lines.append(f"  source: {item.source}")
        lines.append(f"  excerpt: {item.excerpt}")
        if item.citation:
            lines.append(f"  citation: {json.dumps(dict(item.citation), default=str)}")
    user = redact_for_llm("\n".join(lines))
    return RcaPrompt(
        system=system,
        user=user,
        pack_ids=frozenset(item.evidence_id for item in pack),
        input_tokens=estimate_tokens(system) + estimate_tokens(user),
    )


def fixture_rca_payload(user_text: str, *, scenario: str = "latency_spike") -> dict[str, Any]:
    """Deterministic RCA used by FakeLlm / graph default. Cites pack ids only."""
    ids = extract_pack_ids(user_text)
    if not ids:
        raise ValidationError("Fake RCA fixture needs evidence ids in the DATA block.")
    citations = [
        {
            "evidence_id": str(item),
            "source": "simulator",
            "relevance": "Supports the latency hypothesis on the payment path.",
        }
        for item in ids[:2]
    ]
    return {
        "summary": f"{scenario.replace('_', ' ')} on the affected service.",
        "root_cause": "Checkout p99 latency on the payment path after a recent change.",
        "contributing_factors": ["Elevated error logs", "Saturated checkout workers"],
        "confidence": 0.84,
        "status": "hypothesis",
        "evidence_citations": citations,
        "recommended_actions": [
            "Restart checkout workers and watch p99.",
            "Compare the last payment deploy to the latency window.",
        ],
    }


def parse_rca_output(raw: Mapping[str, Any], *, allowed_ids: frozenset[UUID]) -> RcaOutputSchema:
    try:
        parsed = RcaOutputSchema.model_validate(dict(raw))
    except PydanticValidationError as exc:
        raise ValidationError(f"RCA JSON failed schema validation: {exc}") from exc
    if not parsed.evidence_citations:
        raise ValidationError("RCA JSON must cite at least one evidence_id.")
    unknown = [
        str(item.evidence_id)
        for item in parsed.evidence_citations
        if item.evidence_id not in allowed_ids
    ]
    if unknown:
        raise ValidationError(
            f"RCA cited evidence_id values that are not in the pack: {', '.join(unknown)}."
        )
    return parsed


class FixtureLlm:
    """Application-layer default. Same fixture as infrastructure FakeLlm."""

    def complete_json(self, *, system: str, user: str) -> LlmJsonResult:
        payload = fixture_rca_payload(user)
        return LlmJsonResult(
            data=payload,
            model_id=FAKE_MODEL_ID,
            input_tokens=estimate_tokens(system) + estimate_tokens(user),
            output_tokens=estimate_tokens(json.dumps(payload)),
        )


def generate_rca(
    *,
    incident_id: str,
    service: str,
    scenario: str,
    pack: Sequence[EvidencePackItem],
    llm: LlmClient | None = None,
) -> RcaGeneration:
    """Call the LLM at most twice. Ungrounded citations or bad JSON escalate."""
    prompt = assemble_rca_prompt(
        incident_id=incident_id,
        service=service,
        scenario=scenario,
        pack=pack,
    )
    client = llm or FixtureLlm()
    last_error = "RCA generation failed."
    for attempt in range(1, 3):
        try:
            result = client.complete_json(system=prompt.system, user=prompt.user)
            parsed = parse_rca_output(result.data, allowed_ids=prompt.pack_ids)
            report = _to_report(
                incident_id=incident_id,
                parsed=parsed,
                model_id=result.model_id,
                input_tokens=result.input_tokens,
                output_tokens=result.output_tokens,
            )
            if parsed.confidence < CONFIDENCE_THRESHOLD:
                return RcaGeneration(
                    outcome="escalated",
                    escalate_reason=EscalateReason.LOW_CONFIDENCE,
                    report=report,
                    payload=report.as_dict() if report else parsed.model_dump(mode="json"),
                    attempts=attempt,
                    prompt=prompt,
                )
            return RcaGeneration(
                outcome="pending_review",
                escalate_reason=None,
                report=report,
                payload=report.as_dict() if report else parsed.model_dump(mode="json"),
                attempts=attempt,
                prompt=prompt,
            )
        except (ValidationError, TypeError, ValueError) as exc:
            last_error = str(exc)
    return RcaGeneration(
        outcome="escalated",
        escalate_reason=EscalateReason.AGENT_FAILURE,
        report=None,
        payload={"error": last_error},
        attempts=2,
        prompt=prompt,
    )


def report_from_payload(payload: Mapping[str, Any]) -> RcaReport | None:
    """Rehydrate a persisted-shaped RCA dict (runner drain / tests)."""
    report_id = payload.get("id")
    incident_id = payload.get("incident_id")
    citations_raw = payload.get("evidence_citations") or []
    if not report_id or not incident_id:
        return None
    citations = [
        RcaCitation(
            evidence_id=UUID(str(item["evidence_id"])),
            source=str(item.get("source") or ""),
            relevance=str(item.get("relevance") or ""),
        )
        for item in citations_raw
        if isinstance(item, Mapping) and item.get("evidence_id")
    ]
    if not citations:
        return None
    created = payload.get("created_at")
    created_at = None
    if isinstance(created, str) and created:
        text = created[:-1] + "+00:00" if created.endswith("Z") else created
        created_at = datetime.fromisoformat(text)
    return RcaReport(
        id=UUID(str(report_id)),
        incident_id=UUID(str(incident_id)),
        version=int(payload.get("version") or 1),
        version_kind=RcaVersionKind(str(payload.get("version_kind") or "original")),
        summary=str(payload.get("summary") or ""),
        root_cause=str(payload.get("root_cause") or ""),
        contributing_factors=list(payload.get("contributing_factors") or []),
        confidence=float(payload.get("confidence") or 0),
        finding_status=RcaFindingStatus(str(payload.get("status") or "hypothesis")),
        review_status=RcaReviewStatus(str(payload.get("review_status") or "pending_review")),
        citations=citations,
        recommended_actions=list(payload.get("recommended_actions") or []),
        model_id=str(payload.get("model_id") or FAKE_MODEL_ID),
        input_tokens=int(payload.get("input_tokens") or 0),
        output_tokens=int(payload.get("output_tokens") or 0),
        created_at=created_at or datetime.now(timezone.utc),
    )


def _to_report(
    *,
    incident_id: str,
    parsed: RcaOutputSchema,
    model_id: str,
    input_tokens: int,
    output_tokens: int,
) -> RcaReport | None:
    resolved = incident_id_from_state(incident_id)
    if resolved is None:
        return None
    finding = RcaFindingStatus(parsed.status)
    if parsed.confidence < CONFIDENCE_THRESHOLD:
        finding = RcaFindingStatus.HYPOTHESIS
    return RcaReport.create(
        incident_id=resolved,
        summary=parsed.summary,
        root_cause=parsed.root_cause,
        contributing_factors=parsed.contributing_factors,
        confidence=parsed.confidence,
        finding_status=finding,
        citations=[
            RcaCitation(
                evidence_id=item.evidence_id,
                source=item.source,
                relevance=item.relevance,
            )
            for item in parsed.evidence_citations
        ],
        recommended_actions=parsed.recommended_actions,
        model_id=model_id,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        review_status=RcaReviewStatus.PENDING_REVIEW,
    )
