"""CLI: ``uv run python -m aegis.application.investigation --scenario latency_spike``."""

from __future__ import annotations

import argparse
import json
import sys

from aegis.application.investigation.graph import draw_investigation_mermaid
from aegis.application.investigation.run import invoke_investigation


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Run the AEGIS LangGraph investigation skeleton (no OpenSearch, no Claude).",
    )
    parser.add_argument("--service", default="payment")
    parser.add_argument(
        "--scenario",
        default="latency_spike",
        help="FR-083 id: latency_spike, db_exhaustion, bad_deployment, dependency_failure, …",
    )
    parser.add_argument("--thread-id", default=None)
    parser.add_argument(
        "--resume",
        default=None,
        help="After an interrupt: approve or reject (same --thread-id).",
    )
    parser.add_argument("--mermaid", action="store_true", help="Print graph topology and exit.")
    args = parser.parse_args(argv)

    if args.mermaid:
        print(draw_investigation_mermaid())
        return 0

    result = invoke_investigation(
        service=args.service,
        scenario=args.scenario,
        thread_id=args.thread_id,
        resume=args.resume,
    )
    printable = {
        key: value
        for key, value in result.items()
        if not key.startswith("_")
    }
    interrupts = result.get("__interrupt__")
    print(json.dumps(printable, indent=2, default=str))
    if interrupts:
        print(
            "\nPaused (interrupt). Resume with the same --thread-id:\n"
            f"  uv run python -m aegis.application.investigation "
            f"--scenario {args.scenario} --thread-id {result['_thread_id']} --resume approve",
            file=sys.stderr,
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
