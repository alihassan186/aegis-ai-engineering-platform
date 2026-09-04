---
doc_type: incident_report
service: payment
date: 2026-04-12
scenario: latency_spike
severity: high
incident_id: INC-2026-0412
status: published
---

# INC-2026-0412 — Payment authorize latency (closed)

**State:** closed  
**Window:** 2026-04-12 14:05–15:40 UTC  
**Fingerprint (v0.3 rule):** `v1|payment|latency_spike|2026-04-12T14`

## Summary

Checkout authorize p99 moved from ~15 ms to ~800–900 ms. Payment stayed up (HTTP 200) but degraded. One open incident; duplicate alerts that hour were collapsed.

## Timeline

| UTC | Event |
| --- | --- |
| 14:05 | First customer reports “pay button spins.” |
| 14:08 | Webhook ingest created this incident (`latency_spike` on payment). |
| 14:12 | Traces: payment span ~850 ms; user/inventory unchanged. |
| 14:40 | Card-network edge in eu-west-1 shedding; our client had no deadline. |
| 15:10 | Deadline 400 ms + fail-open to “retry payment” UX shipped (approved). |
| 15:40 | p99 < 50 ms; verified; closed. |

## Evidence (summary, not raw ticks)

- Metric: `payment.latency_ms` p99 ≈ 850 vs healthy 12.
- Traces: single slow hop inside payment, not order retries (yet).
- Deploy: **no** user version bump (rules out `bad_deployment`).

## Root cause

Payment HTTP client waited on a degraded card-network path with **no timeout**. Not connection-pool exhaustion (order stayed healthy; no `too many clients`).

## Fix

Client deadline 400 ms; metric `payment.outbound_timeouts`. Runbook updated: `payment-latency-spike.md`.

## Follow-ups

- Add budget for outbound calls in SLOs.
- Knowledge Agent should retrieve this report for “checkout pay is slow” queries.
