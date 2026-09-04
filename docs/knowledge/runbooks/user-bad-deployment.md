---
doc_type: runbook
service: user
date: 2026-07-09
scenario: bad_deployment
status: published
severity: critical
---

# Runbook — Bad user deployment

**Scenario id:** `bad_deployment`  
**Symptom:** `user` is **down**. Logs show 5xx on `/session` and `/login`. Simulator emits a **version bump** on the deployment event. Checkout cannot start because order depends on user.

## Immediate checks (read-only)

1. Deployment event: new `version` on **user** in the last 15 minutes. No version change → look at `memory_leak` or dependency, not this page.
2. Error rate: 5xx, not slow 200s (slow 200s = latency or leak).
3. Canary vs full bake: if one AZ is down and others healthy, rollback that task set only.
4. Config typo (empty JWT secret, bad issuer) often ships with the same version bump.

## Likely causes

- Breaking API contract (session cookie rename) shipped without order/BFF change.
- Missing env on the new task definition.
- Migration ran against the wrong schema.

## Mitigation (human-approved writes)

- Rollback user to the previous task definition (high-risk-write — approval).
- Do not “fix forward” on a down login path unless rollback is impossible.
- Keep payment/inventory running; they are not the blast radius.

## Escalate

Customer-visible login outage → incident commander + release engineer. RCA: `INC-2026-0709`.
