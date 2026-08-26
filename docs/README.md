# AEGIS Documentation

Design and architecture documentation for the Autonomous Engineering & Incident Response System.

This documentation defines the **product intent, requirements, architecture, security posture, and key engineering decisions** for AEGIS. It describes what we are building and why — not what has been implemented yet.

---

## Documentation map

| Area | Document | Purpose |
|---|---|---|
| **Product** | [Product vision](product/product-vision.md) | Mission, users, value proposition, scope, and success criteria |
| **Requirements** | [Functional requirements](requirements/functional-requirements.md) | Capabilities the system must deliver |
| | [Non-functional requirements](requirements/non-functional-requirements.md) | Reliability, security, performance, and operability constraints |
| | [SLOs and SLIs](requirements/slos-and-slis.md) | Service level objectives and indicators |
| | [Risk register](requirements/risk-register.md) | Product, technical, and operational risks |
| **Architecture** | [Platform overview (diagrams)](architecture/platform-overview.md) | **Start here** — full visual map: services, data flows, agents, AWS |
| | [System context](architecture/context.md) | C4 Level 1 — actors, external systems, and boundaries |
| | [System boundaries](architecture/system-boundaries.md) | In-scope vs out-of-scope, trust zones, data flows |
| | [Incident flow](architecture/incident-flow.md) | End-to-end investigation and remediation lifecycle |
| **Security** | [Threat model](security/threat-model.md) | Threat actors, attack surfaces, mitigations, and residual risk |
| **ADRs** | [Architecture Decision Records](adr/) | Durable record of significant technical decisions |

---

## Architecture Decision Records

| ADR | Title | Status |
|---|---|---|
| [ADR-001](adr/ADR-001-modular-monolith.md) | Adopt a modular monolith as the initial architecture | Accepted |
| [ADR-002](adr/ADR-002-postgresql.md) | Use PostgreSQL as the system of record | Accepted |
| [ADR-003](adr/ADR-003-event-driven-investigation.md) | Use event-driven processing for investigation workflows | Accepted |
| [ADR-004](adr/ADR-004-aws-bedrock.md) | Use Amazon Bedrock as the primary LLM provider | Accepted |

---

## How to read this documentation

1. Start with **product vision** to understand the problem and intended outcomes.
2. Review **functional and non-functional requirements** to understand constraints.
3. Read **architecture** documents for system structure and data flows.
4. Review the **threat model** before designing agents, tools, or integrations.
5. Consult **ADRs** when making or reviewing technical decisions.

---

## Conventions

- **Requirement IDs** use prefixes: `FR-` (functional), `NFR-` (non-functional), `SLO-` (service level).
- **Risk IDs** use prefix `RISK-`.
- **Threat IDs** use prefix `THR-`.
- ADRs follow the format: Context → Problem → Decision → Alternatives → Trade-offs → Consequences.
- Documents describe the **target architecture**. Implementation status is tracked separately in the codebase and release notes.
