---
doc_type: catalog
service: platform
date: 2026-09-05
status: published
---

# Checkout estate — service map

Canonical service ids match the production simulator (`user`, `order`, `payment`, `inventory`, `notification`). Status in the simulator is data (`healthy` / `degraded` / `down`), not five real clusters.

| Id | Role | Depends on | Typical RAG filters |
| --- | --- | --- | --- |
| `user` | Session, profile, authn edge | — | `service: user` |
| `inventory` | Stock reservation | — | `service: inventory` |
| `payment` | Authorize / capture | — | `service: payment` |
| `order` | Checkout orchestration | `user`, `inventory`, `payment` | `service: order` |
| `notification` | Email / push / SMS queue | — | `service: notification` |

## Failure scenarios (FR-083)

| Scenario | Primary service | Also degraded |
| --- | --- | --- |
| `latency_spike` | payment | — |
| `db_exhaustion` | payment | order |
| `memory_leak` | user | — |
| `bad_deployment` | user | — |
| `queue_backlog` | notification | — |
| `dependency_failure` | order | — |

When a query names a scenario, retrieve the matching **runbook** and **incident_report**. Do not retrieve live Postgres tickets.
