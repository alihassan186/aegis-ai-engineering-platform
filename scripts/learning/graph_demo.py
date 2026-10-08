"""Learning demo: one whole investigation, in memory. No Docker, no AWS.

Run (pick a scenario):
    AEGIS_SKIP_DOTENV=1 uv run python scripts/learning/graph_demo.py latency_spike
    AEGIS_SKIP_DOTENV=1 uv run python scripts/learning/graph_demo.py db_exhaustion
    AEGIS_SKIP_DOTENV=1 uv run python scripts/learning/graph_demo.py dependency_failure
    AEGIS_SKIP_DOTENV=1 uv run python scripts/learning/graph_demo.py dependency_failure --resume approve

Scenarios: db_exhaustion, memory_leak, latency_spike, bad_deployment,
queue_backlog, dependency_failure. Real code path: the same graph the worker runs,
with in-memory ports (``SpecialistPorts.memory()``) and the fixture LLM.
"""

from __future__ import annotations

import argparse

from aegis.application.investigation.collect import SpecialistPorts
from aegis.application.investigation.graph import draw_investigation_mermaid
from aegis.application.investigation.run import invoke_investigation

SERVICE_FOR = {
    "db_exhaustion": "payment",
    "memory_leak": "user",
    "latency_spike": "payment",
    "bad_deployment": "user",
    "queue_backlog": "notification",
    "dependency_failure": "order",
}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("scenario", nargs="?", default="latency_spike", choices=sorted(SERVICE_FOR))
    parser.add_argument("--resume", choices=["approve", "reject"], default=None)
    parser.add_argument("--no-mermaid", action="store_true")
    args = parser.parse_args()

    ports = SpecialistPorts.memory()
    # Keep one saver so a pause can be resumed with the same thread id.
    from langgraph.checkpoint.memory import InMemorySaver

    saver = InMemorySaver()
    incident_id = "INC-LEARN-0001"
    result = invoke_investigation(
        service=SERVICE_FOR[args.scenario],
        scenario=args.scenario,
        incident_id=incident_id,
        checkpointer=saver,
        ports=ports,
    )
    if args.resume and result.get("__interrupt__"):
        print(f"(paused; resuming with {args.resume!r})\n")
        result = invoke_investigation(
            service=SERVICE_FOR[args.scenario],
            scenario=args.scenario,
            incident_id=incident_id,
            checkpointer=saver,
            resume=args.resume,
            ports=ports,
        )

    print(f"scenario : {args.scenario}")
    print(f"status   : {result.get('status') or 'paused (waiting for a human)'}")
    print(f"hops     : {result.get('hops')}")
    print(f"escalate : {result.get('escalate_reason') or '-'}")
    print("\n-- log (what each node decided) --")
    for line in result.get("log", []):
        print("  ", line)
    print("\n-- evidence collected --")
    for item in result.get("evidence", []):
        body = item.get("summary") or item.get("text") or ""
        print("  ", item.get("collector"), "|", str(body)[:70])
    rca = result.get("rca") or {}
    if rca:
        print("\n-- RCA --")
        print("   summary    :", rca.get("summary"))
        print("   confidence :", rca.get("confidence"))
        print("   citations  :", len(rca.get("evidence_citations", [])))
    interrupts = result.get("__interrupt__")
    if interrupts:
        print("\n-- interrupt payload --")
        print("  ", interrupts[0].value)

    if not args.no_mermaid:
        print("\n-- graph (paste into https://mermaid.live) --")
        print(draw_investigation_mermaid())


if __name__ == "__main__":
    main()
