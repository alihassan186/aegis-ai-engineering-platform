# Functional Requirements

**Document owner:** Product / Engineering  
**Status:** Draft  
**Last updated:** 2026-08-26 (FR-009, FR-019, FR-027–029, FR-057–059, FR-066–067 added)

Requirements are organized by capability area. Each requirement has a unique ID, priority, and target release.

**Priority legend:** `P0` = must-have for release · `P1` = should-have · `P2` = nice-to-have

---

## 1. Incident management


| ID     | Requirement                                                                                                            | Priority | Target |
| ------ | ---------------------------------------------------------------------------------------------------------------------- | -------- | ------ |
| FR-001 | The system shall ingest incident signals from external sources (alarms, webhooks, manual creation)                     | P0       | v0.2   |
| FR-002 | The system shall assign a unique identifier and track lifecycle state for each incident                                | P0       | v0.2   |
| FR-003 | Incident states shall include at minimum: `open`, `investigating`, `identified`, `remediating`, `resolved`, `closed`   | P0       | v0.2   |
| FR-004 | The system shall record timestamps for each state transition                                                           | P0       | v0.2   |
| FR-005 | The system shall associate incidents with affected services, severity, and on-call owner                               | P0       | v0.2   |
| FR-006 | The system shall support manual incident creation via API                                                              | P1       | v0.2   |
| FR-007 | The system shall deduplicate incident signals representing the same underlying issue                                   | P1       | v0.3   |
| FR-008 | The system shall link related incidents (same root cause, same service)                                                | P2       | v0.5   |
| FR-009 | The system shall support listing and filtering incidents by state, severity, affected service, owner, and created date | P0       | v0.2   |


---



## 2. Evidence collection


| ID     | Requirement                                                                                                                      | Priority | Target |
| ------ | -------------------------------------------------------------------------------------------------------------------------------- | -------- | ------ |
| FR-010 | The system shall collect log evidence from configured observability sources                                                      | P0       | v0.5   |
| FR-011 | The system shall collect metric evidence (anomalies, threshold breaches)                                                         | P0       | v0.5   |
| FR-012 | The system shall collect distributed trace evidence                                                                              | P1       | v0.5   |
| FR-013 | The system shall retrieve recent deployment history for affected services                                                        | P0       | v0.5   |
| FR-014 | The system shall search source code repositories for relevant files and changes                                                  | P0       | v0.5   |
| FR-015 | The system shall retrieve runbooks and architecture documentation via RAG                                                        | P0       | v0.4   |
| FR-016 | The system shall search historical incident records for similar past events                                                      | P1       | v0.4   |
| FR-017 | Each evidence item shall include source, timestamp, content reference, and retrieval metadata                                    | P0       | v0.5   |
| FR-018 | The system shall store evidence items linked to the parent incident                                                              | P0       | v0.5   |
| FR-019 | The system shall redact detected secrets and sensitive patterns from evidence before storage and before inclusion in LLM context | P0       | v0.5   |


---



## 3. Investigation & orchestration


| ID     | Requirement                                                                                                    | Priority | Target |
| ------ | -------------------------------------------------------------------------------------------------------------- | -------- | ------ |
| FR-020 | The system shall initiate an automated investigation workflow when an incident is opened                       | P0       | v0.5   |
| FR-021 | An orchestration agent shall plan and delegate evidence collection to specialized agents                       | P0       | v0.5   |
| FR-022 | Investigation progress shall be trackable via API (steps completed, pending, failed)                           | P0       | v0.5   |
| FR-023 | The system shall support pausing and resuming investigations                                                   | P1       | v0.5   |
| FR-024 | The system shall allow manual evidence addition by engineers during an investigation                           | P1       | v0.5   |
| FR-025 | The system shall escalate to a human when investigation confidence is below threshold                          | P0       | v0.5   |
| FR-026 | The system shall enforce a maximum investigation duration before mandatory escalation                          | P1       | v0.5   |
| FR-027 | The system shall notify assigned on-call owner or engineer when an RCA report is ready for review              | P0       | v0.5   |
| FR-028 | The system shall notify relevant engineers when an investigation is escalated due to low confidence or timeout | P0       | v0.5   |
| FR-029 | The system shall notify approvers when a remediation action requires human authorization                       | P0       | v0.9   |


---



## 4. Root cause analysis


| ID     | Requirement                                                                                                       | Priority | Target |
| ------ | ----------------------------------------------------------------------------------------------------------------- | -------- | ------ |
| FR-030 | The system shall produce a structured RCA report for each investigated incident                                   | P0       | v0.5   |
| FR-031 | Every RCA conclusion shall cite specific evidence items                                                           | P0       | v0.5   |
| FR-032 | RCA output shall include: summary, root cause, contributing factors, confidence score, and recommended next steps | P0       | v0.5   |
| FR-033 | The system shall distinguish between confirmed root cause and hypothesis                                          | P0       | v0.5   |
| FR-034 | Engineers shall be able to accept, reject, or amend RCA conclusions                                               | P0       | v0.5   |
| FR-035 | Amended RCAs shall be stored with original and revised versions                                                   | P1       | v0.5   |


---



## 5. Knowledge retrieval (RAG)


| ID     | Requirement                                                                                     | Priority | Target |
| ------ | ----------------------------------------------------------------------------------------------- | -------- | ------ |
| FR-040 | The system shall ingest and index engineering documentation (runbooks, ADRs, architecture docs) | P0       | v0.4   |
| FR-041 | The system shall ingest and index historical incident reports                                   | P1       | v0.4   |
| FR-042 | Retrieval shall support metadata filtering (service, doc type, date range)                      | P0       | v0.4   |
| FR-043 | Retrieval shall support hybrid search (keyword + semantic)                                      | P1       | v0.4   |
| FR-044 | Retrieved context shall include source citations (document, section, chunk)                     | P0       | v0.4   |
| FR-045 | The system shall support re-indexing when source documents change                               | P1       | v0.4   |


---



## 6. Remediation


| ID     | Requirement                                                                                                                            | Priority | Target |
| ------ | -------------------------------------------------------------------------------------------------------------------------------------- | -------- | ------ |
| FR-050 | The system shall recommend remediation actions based on RCA                                                                            | P0       | v0.9   |
| FR-051 | Each remediation recommendation shall include risk classification                                                                      | P0       | v0.9   |
| FR-052 | Risk classifications shall be: `read`, `low-risk-write`, `high-risk-write`, `destructive`                                              | P0       | v0.9   |
| FR-053 | `high-risk-write` actions shall require human approval before execution; `destructive` actions shall be denied and never executed      | P0       | v0.9   |
| FR-054 | The system shall execute approved remediation actions through the tool gateway                                                         | P0       | v0.9   |
| FR-055 | The system shall verify remediation outcome after execution                                                                            | P0       | v0.9   |
| FR-056 | Failed remediation shall trigger rollback recommendation or human escalation                                                           | P0       | v0.9   |
| FR-057 | The system shall create an approval request record for each `high-risk-write` remediation action pending authorization                 | P0       | v0.9   |
| FR-058 | The system shall record approval decisions with approver identity, timestamp, action reference, and decision (`approved` / `rejected`) | P0       | v0.9   |
| FR-059 | The system shall expire pending approval requests after a configurable timeout and notify the incident owner                           | P1       | v0.9   |


---



## 7. Tool gateway & MCP


| ID     | Requirement                                                                                                             | Priority | Target |
| ------ | ----------------------------------------------------------------------------------------------------------------------- | -------- | ------ |
| FR-060 | All agent tool invocations shall pass through a centralized gateway                                                     | P0       | v0.6   |
| FR-061 | The gateway shall enforce authorization based on agent identity and action type                                         | P0       | v0.6   |
| FR-062 | The gateway shall log every tool invocation with inputs, outputs, and decision                                          | P0       | v0.6   |
| FR-063 | The gateway shall enforce rate limits per tool and per agent                                                            | P1       | v0.6   |
| FR-064 | The gateway shall deny tool calls that violate policy rules                                                             | P0       | v0.6   |
| FR-065 | Tools shall be exposed via MCP-compatible interfaces                                                                    | P1       | v0.6   |
| FR-066 | The system shall allow administrators to define and manage tool policy rules (allowed tools, action classes, scopes)    | P0       | v0.6   |
| FR-067 | The tool gateway shall evaluate policy rules on every invocation and return an explicit allow/deny decision with reason | P0       | v0.6   |


---



## 8. Authentication & authorization


| ID     | Requirement                                                                     | Priority | Target |
| ------ | ------------------------------------------------------------------------------- | -------- | ------ |
| FR-070 | The system shall authenticate API users via token-based authentication          | P0       | v0.2   |
| FR-071 | The system shall support role-based access control (RBAC)                       | P0       | v0.2   |
| FR-072 | Roles shall include at minimum: `viewer`, `engineer`, `approver`, `admin`       | P0       | v0.2   |
| FR-073 | Only `approver` and `admin` roles shall authorize high-risk remediation actions | P0       | v0.9   |
| FR-074 | Agent service accounts shall have scoped, least-privilege permissions           | P0       | v0.6   |


---



## 9. Production simulator


| ID     | Requirement                                                                                                                   | Priority | Target |
| ------ | ----------------------------------------------------------------------------------------------------------------------------- | -------- | ------ |
| FR-080 | The simulator shall model a multi-service application ecosystem                                                               | P0       | v0.3   |
| FR-081 | The simulator shall generate realistic logs, metrics, and traces                                                              | P0       | v0.3   |
| FR-082 | The simulator shall support configurable failure scenarios                                                                    | P0       | v0.3   |
| FR-083 | Failure scenarios shall include: DB exhaustion, memory leak, latency spike, bad deployment, queue backlog, dependency failure | P0       | v0.3   |
| FR-084 | The simulator shall emit incident signals consumable by AEGIS                                                                 | P0       | v0.3   |


---



## 10. Evaluation & benchmarking


| ID     | Requirement                                                                    | Priority | Target |
| ------ | ------------------------------------------------------------------------------ | -------- | ------ |
| FR-090 | The system shall maintain a golden dataset of incidents with expected outcomes | P0       | v0.8   |
| FR-091 | The system shall measure RCA accuracy against the golden dataset               | P0       | v0.8   |
| FR-092 | The system shall measure evidence precision and retrieval recall               | P0       | v0.8   |
| FR-093 | The system shall measure unsafe action rate (policy violations attempted)      | P0       | v0.8   |
| FR-094 | Evaluation results shall be stored and comparable across releases              | P0       | v0.8   |


---



## 11. Audit & reporting


| ID     | Requirement                                                                              | Priority | Target |
| ------ | ---------------------------------------------------------------------------------------- | -------- | ------ |
| FR-100 | The system shall maintain an immutable audit log of all agent actions and decisions      | P0       | v0.6   |
| FR-101 | The system shall generate post-incident reports (timeline, evidence, RCA, actions taken) | P0       | v0.5   |
| FR-102 | Audit logs shall be retained for a configurable period (minimum 90 days)                 | P1       | v0.7   |
| FR-103 | The system shall export incident reports in structured format (JSON, Markdown)           | P1       | v0.5   |


---



## 12. API & integration


| ID     | Requirement                                                              | Priority | Target |
| ------ | ------------------------------------------------------------------------ | -------- | ------ |
| FR-110 | The system shall expose a RESTful HTTP API for all core operations       | P0       | v0.2   |
| FR-111 | The API shall be documented via OpenAPI specification                    | P0       | v0.2   |
| FR-112 | The system shall provide a health check endpoint                         | P0       | v0.1   |
| FR-113 | The system shall support webhook ingestion for external incident sources | P1       | v0.3   |
| FR-114 | The system shall integrate with GitHub for code search and PR creation   | P1       | v0.6   |


---



## Related documents

- [Non-functional requirements](non-functional-requirements.md)
- [Product vision](../product/product-vision.md)
- [Incident flow (architecture)](../architecture/incident-flow.md)
- [Threat model](../security/threat-model.md)

