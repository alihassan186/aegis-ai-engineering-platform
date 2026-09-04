---
doc_type: runbook
service: notification
date: 2026-04-22
scenario: queue_backlog
status: published
severity: medium
---

# Runbook — Notification queue backlog

**Scenario id:** `queue_backlog`  
**Symptom:** `notification` is `degraded`. Queue depth metric rises. Checkout and payment can still succeed; users report missing order-confirmation email / push.

## Immediate checks (read-only)

1. Queue depth vs publish rate vs consume rate. Depth up + consume ~0 = worker dead. Depth up + consume healthy = publisher burst.
2. Dead-letter count. A poison payload will stall a single partition.
3. Provider (SES / FCM) 429 or 5xx — downstream, not our publish path.
4. Do not page payments. This scenario does not degrade `payment`.

## Likely causes

- Consumer scaled to zero after a bad deploy of the worker.
- Retry storm after a provider outage.
- A campaign job publishing marketing mail on the same queue as transactional (priority inversion).

## Mitigation (human-approved writes)

- Separate transactional vs marketing queues if they share a worker.
- Scale consumers; replay DLQ after fixing the payload.
- Pause the campaign publisher first if it is the burst.

## Escalate

If transactional depth > 100k or age > 30 min, page notifications. RCA: `INC-2026-0422`.
