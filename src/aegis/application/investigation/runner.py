"""``InvestigationRunner`` that invokes the compiled StateGraph. No Claude."""

from __future__ import annotations

import logging

from langgraph.checkpoint.memory import InMemorySaver

from aegis.application.evidence.record_evidence import CollectingEvidenceRecorder
from aegis.application.investigation.collect import SpecialistPorts
from aegis.application.investigation.rca import report_from_payload
from aegis.application.investigation.run import invoke_investigation
from aegis.domain.evidence.entity import Evidence
from aegis.domain.rca.entity import RcaReport

logger = logging.getLogger(__name__)


class LangGraphInvestigationRunner:
    """One compiled graph; checkpointer keyed by ``thread_id`` = ``incident_id``."""

    def __init__(
        self,
        checkpointer: InMemorySaver | None = None,
        ports: SpecialistPorts | None = None,
    ) -> None:
        self._checkpointer = checkpointer or InMemorySaver()
        self._recorded: list[Evidence] = []
        resolved = ports or SpecialistPorts.memory()
        if resolved.recorder is None:
            resolved = SpecialistPorts(
                observability=resolved.observability,
                code_search=resolved.code_search,
                retrieve=resolved.retrieve,
                recorder=CollectingEvidenceRecorder(self._recorded),
                llm=resolved.llm,
            )
        self._ports = resolved
        self._rca_reports: list[RcaReport] = []

    def start(
        self,
        *,
        incident_id: str,
        service: str,
        scenario: str,
        correlation_id: str,
    ) -> None:
        extra = {
            "correlation_id": correlation_id,
            "incident_id": incident_id,
        }
        logger.info(
            "starting investigation graph service=%s scenario=%s thread_id=%s",
            service,
            scenario,
            incident_id,
            extra=extra,
        )
        result = invoke_investigation(
            service=service,
            scenario=scenario,
            incident_id=incident_id,
            thread_id=incident_id,
            checkpointer=self._checkpointer,
            correlation_id=correlation_id,
            ports=self._ports,
        )
        status = result.get("status") or "paused"
        logger.info("investigation graph returned status=%s", status, extra=extra)
        self._capture_rca(result)

    def drain_recorded_evidence(self) -> list[Evidence]:
        """Evidence minted during the last ``start``. Cleared after the read."""
        items = list(self._recorded)
        self._recorded.clear()
        return items

    def drain_recorded_rca(self) -> list[RcaReport]:
        items = list(self._rca_reports)
        self._rca_reports.clear()
        return items

    def _capture_rca(self, result: dict[str, object]) -> None:
        payload = result.get("rca")
        if not isinstance(payload, dict):
            return
        report = report_from_payload(payload)
        if report is not None:
            self._rca_reports.append(report)
