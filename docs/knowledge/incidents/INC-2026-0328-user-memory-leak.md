---
doc_type: incident_report
service: user
date: 2026-03-28
scenario: memory_leak
severity: high
incident_id: INC-2026-0328
status: published
---

# INC-2026-0328 — User service in-process session cache leak (closed)

**State:** closed  
**Window:** 2026-03-28 16:00–19:20 UTC

## Summary

User RSS climbed for three hours. Login mostly 200, p95 session read grew. Service stayed `degraded`, never `down` (unlike INC-2026-0709).

## Timeline

| UTC | Event |
| --- | --- |
| 16:00 | Memory gauge stair-step (matches simulator leak ticks, then cap). |
| 16:40 | Full GC every 20s; no new user version. |
| 17:15 | Found `SESSION_CACHE_UNBOUNDED=true` on a canary from a debug flag. |
| 18:00 | Flag off; rolling bounce of user (approved). |
| 19:20 | Heap stable; closed. |

## Evidence (summary)

- Memory metric: monotonic increase, then plateau (cgroup / synthetic cap).
- No deployment event on user that afternoon.
- Heap dump: `SessionRecord` retained by a static `HashMap`.

## Root cause

Debug session cache shipped without max size or TTL. Each login added an entry forever.

## Fix

Cache max 10k + 15 min TTL; flag default false. Runbook: `user-memory-leak.md`.

## Follow-ups

- Production must cap leaks; the simulator cap is only to protect the laptop.
