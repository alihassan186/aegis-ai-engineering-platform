---
doc_type: runbook
service: order
related_services: payment, user, inventory
date: 2026-08-14
scenario: dependency_failure
status: published
severity: high
---

# Runbook — Order dependency failure

**Scenario id:** `dependency_failure`  
**Symptom:** `order` is `degraded`. Place-order spans show **timeouts calling a downstream** (user, inventory, or payment). Downstream status may still be `healthy` in the catalog — the failure is the call path (deadline, mesh, wrong host), not necessarily the callee being down.

## Immediate checks (read-only)

1. Which dependency timed out? Trace `order` parent + child spans. Simulator marks order degraded and times out the downstream call.
2. If **payment** is also `degraded` with pool errors, switch to `db_exhaustion`. If payment p99 is ~850 ms and order is healthy, switch to `latency_spike`.
3. Recent change to order’s base URL / timeout / retry budget.
4. Inventory lock timeouts look like this runbook when only the order→inventory hop fails.

## Likely causes

- Tight deadline (150 ms) on a hop that needs 300 ms.
- Stale service discovery (calling an old payment task).
- Mesh retry + order retry = timeout amplification.

## Mitigation (human-approved writes)

- Raise the specific hop deadline; cut retries to 1.
- Fail a checkout step-open with 503 + `Retry-After` instead of hanging the client.
- Do not restart all five services.

## Escalate

If all three dependencies time out, treat as mesh/core DNS. RCA: `INC-2026-0814`.
