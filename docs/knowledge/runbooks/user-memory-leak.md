---
doc_type: runbook
service: user
date: 2026-03-28
scenario: memory_leak
status: published
severity: high
---

# Runbook — User service memory leak

**Scenario id:** `memory_leak`  
**Symptom:** `user` is `degraded`. RSS / heap gauge climbs each tick and then **caps** (simulator cap exists so the process does not OOM the laptop). Session API slows; login still often 200.

## Immediate checks (read-only)

1. Memory gauge trend: stepwise increase, not a single cliff (cliff is more like `bad_deployment`).
2. GC logs: rising old-gen, frequent full GC, no new version in the last hour.
3. Feature flag that caches sessions in-process (unbounded map) — search recent user commits.
4. Do not confuse with `bad_deployment`: that sets user **down** and emits 5xx + a version bump.

## Likely causes

- In-process session cache without TTL or max size.
- Listener / subscription leak per websocket.
- Debug heap dump left enabled in a canary.

## Mitigation (human-approved writes)

- Disable the unbounded cache flag; bounce **user** only after approval.
- Cap the map (simulator already caps the synthetic gauge — production must cap for real).
- Do not restart payment or order.

## Escalate

If RSS approaches the cgroup limit or user starts 502ing, treat as imminent OOM. RCA: `INC-2026-0328`.
