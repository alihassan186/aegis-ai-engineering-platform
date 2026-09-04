---
doc_type: incident_report
service: notification
date: 2026-04-22
scenario: queue_backlog
severity: medium
incident_id: INC-2026-0422
status: published
---

# INC-2026-0422 — Transactional mail stuck behind campaign (closed)

**State:** closed  
**Window:** 2026-04-22 08:00–12:30 UTC

## Summary

Notification queue depth climbed. Orders and payments succeeded; customers did not get confirmation email. Service `degraded`, not down.

## Timeline

| UTC | Event |
| --- | --- |
| 08:00 | Marketing campaign published 2M jobs on the **same** queue as order-confirm. |
| 08:40 | Depth age > 25 min; on-call opened this incident. |
| 09:10 | Identified shared queue + equal priority. |
| 10:00 | Paused campaign publisher (approved). |
| 11:20 | Transactional drain complete. |
| 12:30 | Closed; split queues scheduled. |

## Evidence (summary)

- `notification.queue_depth` up; consume rate unchanged.
- Payment/order golden signals healthy.
- Campaign job ids dominated the head of the queue.

## Root cause

Priority inversion: marketing and transactional shared one worker and one queue.

## Fix

Paused campaign; later split `notification-transactional` vs `notification-marketing`. Runbook: `notification-queue-backlog.md`.

## Follow-ups

- RAG filter `service=notification` + `doc_type=incident_report` should hit this file, not payment RCAs.
