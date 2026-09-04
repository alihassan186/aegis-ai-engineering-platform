---
doc_type: runbook
service: payment
date: 2026-06-02
scenario: latency_spike
status: published
severity: high
---

# Runbook — Payment latency spike

**Scenario id:** `latency_spike`  
**Symptom:** Checkout authorize p99 rises (simulator healthy baseline is ~12 ms; spike bias is ~850 ms). `payment` is `degraded`. Orders queue behind payment, but `order` may still show healthy.

## Immediate checks (read-only)

1. Confirm the incident fingerprint is `payment` + `latency_spike` (same UTC hour collapses to one open incident).
2. Payment latency metric: compare current p99 to the 12 ms healthy tick. A jump past 500 ms is this runbook, not DB pool exhaustion (that runbook shows connection wait + order degraded together).
3. Trace: payment span duration_ms vs user/inventory spans. If only payment is slow, do not restart user.
4. Recent deploy on **payment** only. A version bump on **user** is `bad_deployment`, not this page.

## Likely causes

- Downstream card-network timeout with a missing deadline (client waits ~1s).
- Hot lock on the authorize row for a popular SKU (less common than network).
- Retry amplification: order retries payment 3× and multiplies load.

## Mitigation (human-approved writes)

- Raise payment client timeout visibility; shed non-checkout authorizes.
- Disable the extra retry on `order → payment` if traces show stacked spans.
- Do **not** scale Postgres first — that is `db_exhaustion`.

## Escalate

If p99 > 2 s or payment flips to `down`, page payments on-call and attach traces. Link historical RCA `INC-2026-0412`.
