---
doc_type: incident_report
service: user
date: 2026-07-09
scenario: bad_deployment
severity: critical
incident_id: INC-2026-0709
status: published
---

# INC-2026-0709 — User 1.14.0 session cookie break (closed)

**State:** closed  
**Window:** 2026-07-09 13:02–13:41 UTC

## Summary

User went **down** after deploy `1.14.0`. Login and session 5xx. Order could not start checkout (depends on user). Not a memory leak: version bump + instant 5xx.

## Timeline

| UTC | Event |
| --- | --- |
| 13:02 | Pipeline promoted user 1.14.0 (deployment event). |
| 13:03 | 5xx on `/login` and `/session`; health failed. |
| 13:08 | Incident opened (`bad_deployment`). |
| 13:18 | Rollback to 1.13.4 approved. |
| 13:28 | User healthy; checkout recovered. |
| 13:41 | Closed; postmortem filed. |

## Evidence (summary)

- Deployment event: `user` version 1.13.4 → 1.14.0.
- Logs: `TypeError` cookie name `sid` vs BFF still sending `session`.
- Payment/inventory metrics flat.

## Root cause

Cookie rename in 1.14.0 without a BFF/order contract change. Blast radius = user down, order blocked.

## Fix

Rollback; 1.14.1 accepts both cookie names. Runbook: `user-bad-deployment.md`.

## Follow-ups

- Contract test: BFF cookie ↔ user session before bake.
- Rollback is the first write, not fix-forward, when login is down.
