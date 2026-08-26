# System Context (C4 Level 1)

**Document owner:** Architecture  
**Status:** Draft  
**Last updated:** 2026-08-26

This document describes AEGIS at the **system context** level — the actors, external systems, and trust boundaries that surround the platform.

---

## 1. Context diagram

```text
                                    ┌─────────────────────┐
                                    │   On-call Engineer  │
                                    │   SRE / Platform    │
                                    └──────────┬──────────┘
                                               │
                                    approves, reviews, triggers
                                               │
┌──────────────────┐                 ┌─────────▼──────────────────────────────────┐
│  Observability   │──logs/metrics──▶│                                            │
│  (CloudWatch,    │   traces/alarms │              A E G I S                       │
│   Datadog, etc.) │                 │   Autonomous Engineering &                   │
└──────────────────┘                 │   Incident Response System                   │
                                     │                                            │
┌──────────────────┐                 │  ┌──────────────────────────────────────┐  │
│  Alerting /      │──incident──────▶│  │  API · Agents · RAG · Tool Gateway  │  │
│  Paging (PagerDuty│   signals      │  └──────────────────────────────────────┘  │
│   Opsgenie)      │                 └─────────┬──────────────────────────────────┘
└──────────────────┘                           │
                                               │ governed tool calls
┌──────────────────┐                           │
│  GitHub          │◀────code search, PRs──────┤
│  (repositories)  │                           │
└──────────────────┘                           │
                                               │
┌──────────────────┐                           │
│  CI/CD           │◀────deploy history────────┤
│  (GitHub Actions)│                           │
└──────────────────┘                           │
                                               │
┌──────────────────┐                           │
│  Production      │◀────health checks─────────┤
│  Simulator       │───synthetic signals──────▶│
│  (dev/test)      │                           │
└──────────────────┘                           │
                                               │
                                     ┌─────────▼──────────┐
                                     │   Amazon Bedrock   │
                                     │   (LLM / embed)    │
                                     └────────────────────┘
```

---

## 2. System description

**AEGIS** is the central platform that:

- Receives incident signals from alerting and observability systems
- Orchestrates AI agents to collect and correlate evidence
- Produces evidence-backed root cause analysis
- Recommends and (with approval) executes controlled remediation
- Stores investigation history and institutional knowledge

AEGIS does **not** replace observability tools, source control, or CI/CD. It integrates with them through governed interfaces.

---

## 3. Actors

| Actor | Description | Interaction |
|---|---|---|
| **On-call engineer** | First responder during production incidents | Creates/views incidents, reviews RCA, approves remediation |
| **SRE / platform engineer** | Owns reliability, observability, and runbooks | Configures integrations, reviews investigation quality, maintains golden datasets |
| **Engineering lead** | Approves high-risk remediation actions | Authorizes write actions via approval workflow |
| **Security reviewer** | Reviews agent permissions and audit logs | Audits tool gateway policies, investigates security events |
| **AEGIS agents** | Automated investigation actors | Collect evidence, synthesize RCA, propose remediation (no direct human identity) |

---

## 4. External systems

| System | Purpose | Integration pattern | Data direction |
|---|---|---|---|
| **Observability platform** | Logs, metrics, traces, alarms | Tool gateway (read-only API) | Inbound to AEGIS |
| **Alerting / paging** | Incident signal source | Webhook / EventBridge | Inbound to AEGIS |
| **GitHub** | Source code, commits, PRs | Tool gateway (read + controlled write) | Bidirectional |
| **CI/CD (GitHub Actions)** | Deployment history, pipeline status | Tool gateway (read-only) | Inbound to AEGIS |
| **Amazon Bedrock** | LLM inference, embeddings | AWS SDK (private VPC endpoint) | Outbound from AEGIS |
| **Amazon OpenSearch** | Vector + keyword search for RAG | AWS SDK | Internal to AEGIS |
| **Amazon RDS (PostgreSQL)** | System of record | Internal | Internal to AEGIS |
| **Amazon SQS / EventBridge** | Async investigation workflows | AWS SDK | Internal to AEGIS |
| **Production simulator** | Synthetic failure scenarios for dev/test | Internal API | Bidirectional (dev only) |

---

## 5. Trust boundaries

```text
┌─────────────────────────────────────────────────────────────────┐
│  TRUST ZONE: External (untrusted input)                         │
│  - Alert payloads                                               │
│  - Retrieved documents (RAG)                                    │
│  - Webhook sources                                              │
└───────────────────────────────┬─────────────────────────────────┘
                                │ validate, sanitize
┌───────────────────────────────▼─────────────────────────────────┐
│  TRUST ZONE: AEGIS application                                  │
│  - API layer (authenticated)                                    │
│  - Agent orchestration                                          │
│  - Policy engine                                                │
└───────────────────────────────┬─────────────────────────────────┘
                                │ authorized tool calls only
┌───────────────────────────────▼─────────────────────────────────┐
│  TRUST ZONE: External integrations (controlled read/write)     │
│  - Observability APIs                                           │
│  - GitHub API                                                   │
│  - Production infrastructure (approval required for writes)       │
└─────────────────────────────────────────────────────────────────┘
```

**Key rule:** LLMs and agents never sit in the "External integrations" trust zone directly. All external access flows through the tool gateway with policy enforcement.

---

## 6. Data flows (summary)

| Flow | Data | Sensitivity |
|---|---|---|
| Alert → AEGIS | Incident metadata, alarm context | Operational |
| Observability → AEGIS | Logs, metrics, traces | May contain PII/secrets — redact before LLM |
| RAG → AEGIS | Documentation, runbooks, past incidents | Untrusted — prompt injection risk |
| AEGIS → Bedrock | Investigation prompts, evidence context | No raw credentials |
| AEGIS → Engineer | RCA report, remediation recommendations | Operational |
| Engineer → AEGIS | Approval decisions, manual evidence | Audit logged |
| AEGIS → GitHub | Code search (read), PR creation (write, approved) | Operational |

---

## 7. Deployment context

Initial deployment target:

- Single AWS account, single region
- VPC with private subnets for application, database, and search
- Public API endpoint via Application Load Balancer
- Bedrock accessed via VPC endpoint (no public internet for LLM calls)

Multi-region and multi-account deployment are out of scope for v1.0.

---

## Related documents

- [System boundaries](system-boundaries.md)
- [Incident flow](incident-flow.md)
- [Threat model](../security/threat-model.md)
- [ADR-001: Modular monolith](../adr/ADR-001-modular-monolith.md)
