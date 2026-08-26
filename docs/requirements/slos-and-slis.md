# SLOs and SLIs

**Document owner:** SRE / Engineering  
**Status:** Draft  
**Last updated:** 2026-08-26

Service Level Indicators (SLIs) measure system behavior. Service Level Objectives (SLOs) define target thresholds. Error budgets represent allowable unreliability before escalation.

---

## 1. SLI definitions

| SLI ID | Name | Measurement | Data source |
|---|---|---|---|
| SLI-001 | API availability | Ratio of successful health + core API responses (non-5xx) to total requests | CloudWatch / application metrics |
| SLI-002 | API latency | p99 response time for core API endpoints | CloudWatch / OpenTelemetry |
| SLI-003 | Investigation success rate | Ratio of investigations reaching `identified` or `resolved` without escalation to total started | Application database |
| SLI-004 | Investigation duration | Time from incident `open` to first evidence-backed RCA | Application database |
| SLI-005 | RAG retrieval latency | p95 time to return ranked results for a query | Application metrics |
| SLI-006 | Tool gateway deny rate | Ratio of policy-denied tool calls to total tool calls | Audit log |
| SLI-007 | Unsafe action attempt rate | Count of blocked high-risk/destructive action attempts | Audit log |
| SLI-008 | Bedrock error rate | Ratio of failed Bedrock invocations to total invocations | CloudWatch / application metrics |
| SLI-009 | Queue processing lag | Time between message enqueue and processing start | SQS metrics |
| SLI-010 | RCA benchmark accuracy | Correct root cause on golden dataset evaluations | Evaluation pipeline |

---

## 2. SLO targets

### v0.2 — Core API (initial SLOs)

| SLO ID | SLI | Target | Window | Error budget |
|---|---|---|---|---|
| SLO-001 | SLI-001 API availability | ≥ 99.5% | 30 days | 3.6 hours downtime |
| SLO-002 | SLI-002 API latency (p99) | < 500ms | 30 days | 0.5% of requests may exceed |

### v0.5 — Investigation platform

| SLO ID | SLI | Target | Window | Error budget |
|---|---|---|---|---|
| SLO-003 | SLI-003 Investigation success rate | ≥ 85% | 30 days | 15% may require escalation |
| SLO-004 | SLI-004 Investigation duration (p95) | < 10 minutes | 30 days | 5% may exceed |
| SLO-005 | SLI-005 RAG retrieval latency (p95) | < 2 seconds | 30 days | 5% may exceed |
| SLO-006 | SLI-008 Bedrock error rate | < 2% | 7 days | Retry + fallback required |

### v0.6 — Tool gateway & security

| SLO ID | SLI | Target | Window | Error budget |
|---|---|---|---|---|
| SLO-007 | SLI-007 Unsafe action attempt rate | 0 (all blocked) | 30 days | Zero tolerance |
| SLO-008 | SLI-006 Tool gateway availability | ≥ 99.9% | 30 days | 43 minutes downtime |

### v0.8 — Evaluation

| SLO ID | SLI | Target | Window | Error budget |
|---|---|---|---|---|
| SLO-009 | SLI-010 RCA benchmark accuracy | ≥ 75% | Per release | Regression blocks release |
| SLO-010 | SLI-009 Queue processing lag (p99) | < 30 seconds | 7 days | Backpressure alert at 60s |

---

## 3. Alerting policy

Alerts fire when SLO burn rate indicates error budget exhaustion:

| Alert | Condition | Severity | Action |
|---|---|---|---|
| API down | SLI-001 < 95% over 5 minutes | Critical | Page on-call |
| API latency degradation | SLI-002 p99 > 1s over 10 minutes | Warning | Investigate |
| Investigation failure spike | SLI-003 < 70% over 1 hour | Warning | Review agent logs |
| Bedrock errors | SLI-008 > 5% over 15 minutes | Warning | Check Bedrock quotas/region |
| Unsafe action attempted | SLI-007 > 0 | Critical | Security review |
| Queue backlog | SLI-009 p99 > 60 seconds | Warning | Scale consumers |
| RCA regression | SLI-010 drops > 5% from baseline | Warning | Block release |

---

## 4. Error budget policy

When an error budget is exhausted within a window:

1. **Freeze non-critical feature work** on the affected component
2. **Prioritize reliability fixes** until budget is restored
3. **Conduct post-mortem** if SLO-001 or SLO-007 is breached
4. **Document** in incident report and update risk register if needed

---

## 5. Exclusions

The following are excluded from availability SLOs:

- Planned maintenance windows (announced ≥ 24 hours ahead)
- Health check endpoint during deployment rolling updates (< 5 minutes)
- Simulator-only environments

---

## Related documents

- [Non-functional requirements](non-functional-requirements.md)
- [Risk register](risk-register.md)
- [Incident flow (architecture)](../architecture/incident-flow.md)
