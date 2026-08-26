# AEGIS Platform Overview — Architecture Diagrams

**Document owner:** Architecture  
**Status:** Draft  
**Last updated:** 2026-08-26

This document provides **visual architecture diagrams** for the full AEGIS platform — services, integrations, databases, agents, events, and data flows.

> **Scope:** These diagrams describe the **target architecture** defined in requirements and ADRs. They represent what we are building, not what is implemented today.

---

## How to read these diagrams

| Diagram | Purpose | Standard |
|---|---|---|
| §1 System context | Who uses AEGIS and what external systems it connects to | C4 Level 1 |
| §2 Container view | Major runtime components and how they communicate | C4 Level 2 |
| §3 Application layers | Internal code structure and dependency direction | Layered architecture |
| §4 Service map | Repository modules mapped to runtime responsibilities | Module view |
| §5 Data stores | What data lives where and why | Data architecture |
| §6 Entity model | Core database entities and relationships | ER diagram |
| §7 Incident sequence | End-to-end request and event flow | UML sequence |
| §8 Agent orchestration | Multi-agent investigation workflow | Flowchart |
| §9 Event-driven flow | EventBridge → SQS → workers | Event architecture |
| §10 Tool gateway | Policy, auth, and external tool access | Security architecture |
| §11 RAG pipeline | Ingestion, indexing, retrieval | Data pipeline |
| §12 AWS deployment | Target cloud infrastructure topology | Infrastructure view |
| §13 Production simulator | Dev/test environment integration | Environment view |

**Recommended reading order:** §1 → §2 → §7 → §8 → §5 → §12

---

## 1. System context (C4 Level 1)

Actors and external systems surrounding AEGIS.

```mermaid
flowchart TB
    subgraph actors["Actors"]
        ENG["On-call Engineer"]
        SRE["SRE / Platform Engineer"]
        LEAD["Engineering Lead"]
        SEC["Security Reviewer"]
    end

    subgraph aegis["AEGIS Platform"]
        PLATFORM["Incident Investigation · RCA · Controlled Remediation"]
    end

    subgraph external["External Systems"]
        OBS["Observability<br/>(CloudWatch / Datadog)"]
        ALERT["Alerting / Paging<br/>(PagerDuty / Opsgenie)"]
        GH["GitHub<br/>(Code · PRs · Commits)"]
        CICD["CI/CD<br/>(GitHub Actions)"]
        BEDROCK["Amazon Bedrock<br/>(LLM · Embeddings)"]
        SIM["Production Simulator<br/>(Dev / Test)"]
    end

    ENG -->|"review RCA · approve remediation"| PLATFORM
    SRE -->|"configure · evaluate · maintain runbooks"| PLATFORM
    LEAD -->|"authorize high-risk actions"| PLATFORM
    SEC -->|"audit policies · review logs"| PLATFORM

    ALERT -->|"incident signals / webhooks"| PLATFORM
    OBS <-->|"logs · metrics · traces (read)"| PLATFORM
    GH <-->|"code search · PR creation (controlled)"| PLATFORM
    CICD -->|"deployment history (read)"| PLATFORM
    PLATFORM -->|"LLM inference · embeddings"| BEDROCK
    SIM <-->|"synthetic signals · failure scenarios"| PLATFORM
```

---

## 2. Container view (C4 Level 2)

Major runtime containers inside AEGIS and their connections.

```mermaid
flowchart TB
    subgraph users["Users & External Signals"]
        USER["Engineers / Approvers"]
        WEBHOOK["Alert Webhooks"]
    end

    subgraph edge["Edge"]
        ALB["Application Load Balancer"]
    end

    subgraph aegis_runtime["AEGIS Runtime — Modular Monolith on ECS/Fargate"]
        API["API Service<br/>(FastAPI)"]
        WORKER["Investigation Worker<br/>(Async Consumer)"]
        ORCH["Agent Orchestrator<br/>(LangGraph)"]
        AGENTS["Specialized Agents"]
        GATEWAY["Tool Gateway<br/>(Policy · Auth · Audit)"]
        RAG["RAG Pipeline<br/>(Ingest · Retrieve)"]
        EVAL["Evaluation Pipeline"]
    end

    subgraph messaging["Event Layer"]
        EB["Amazon EventBridge"]
        SQS["Amazon SQS"]
        DLQ["Dead Letter Queue"]
    end

    subgraph data["Data Layer"]
        PG[("PostgreSQL (RDS)<br/>System of Record")]
        REDIS[("Redis<br/>Cache · Workflow State")]
        OS[("OpenSearch<br/>Vectors · Full-text")]
    end

    subgraph ai["AI Layer"]
        BR["Amazon Bedrock"]
    end

    subgraph external_tools["External Integrations"]
        OBS_API["Observability APIs"]
        GH_API["GitHub API"]
        DEPLOY_API["CI/CD APIs"]
    end

    USER --> ALB --> API
    WEBHOOK --> ALB --> API

    API --> PG
    API --> REDIS
    API --> EB

    EB --> SQS --> WORKER
    SQS -.-> DLQ

    WORKER --> ORCH --> AGENTS
    AGENTS --> GATEWAY
    AGENTS --> RAG
    AGENTS --> BR
    RAG --> OS
    RAG --> BR

    GATEWAY --> OBS_API
    GATEWAY --> GH_API
    GATEWAY --> DEPLOY_API

    AGENTS --> PG
    WORKER --> PG
    GATEWAY --> PG
    API --> OS

    EVAL --> PG
    EVAL --> BR
    EVAL --> ORCH
```

---

## 3. Application layers

Internal layering — dependencies point **inward only**.

```mermaid
flowchart TB
    subgraph presentation["Presentation Layer"]
        ROUTES["FastAPI Routes"]
        WH["Webhook Handlers"]
        OPENAPI["OpenAPI /docs"]
    end

    subgraph application["Application Layer"]
        UC["Use Cases"]
        INV["Investigation Orchestrator"]
        APPROVAL["Approval Workflow"]
        NOTIFY["Notification Service"]
    end

    subgraph domain["Domain Layer"]
        INC["Incident"]
        EVID["Evidence"]
        RCA["RCA Report"]
        REM["Remediation"]
        POL["Policy Rules"]
        AUDIT["Audit Log"]
    end

    subgraph infrastructure["Infrastructure Layer"]
        REPO["PostgreSQL Repositories"]
        CACHE["Redis Client"]
        BEDROCK_C["Bedrock Client"]
        OS_C["OpenSearch Client"]
        SQS_C["SQS / EventBridge Client"]
        EXT["External API Clients"]
    end

    subgraph cross["Cross-cutting"]
        GW["Tool Gateway"]
        AGT["Agent Runtime"]
        RAG_P["RAG Pipeline"]
    end

    ROUTES --> UC
    WH --> UC
    UC --> INC & EVID & RCA & REM & APPROVAL
    INV --> AGT
    APPROVAL --> POL & AUDIT
    NOTIFY --> UC

    UC --> REPO & CACHE & SQS_C
    AGT --> GW & BEDROCK_C & RAG_P
    GW --> EXT & REPO
    RAG_P --> OS_C & BEDROCK_C
    REPO --> INC & EVID & RCA & REM & AUDIT
```

---

## 4. Service & module map

Repository structure mapped to runtime responsibilities.

```mermaid
flowchart LR
    subgraph repo["Repository Modules"]
        direction TB
        SRC["src/aegis/<br/>domain · application · infrastructure"]
        AG["agents/<br/>incident_commander · observability<br/>code · knowledge · rca · remediation"]
        SVC["services/<br/>incident · investigation<br/>approval · deployment"]
        TOOLS["tools/<br/>cloudwatch · github · database · deployment"]
        MCP["mcp/<br/>tool servers · gateway"]
        APPS["apps/<br/>api · simulator · frontend"]
        EVAL_DIR["evaluation/<br/>benchmarks · datasets · metrics"]
        INFRA["infrastructure/cdk/<br/>AWS stacks"]
    end

    subgraph runtime["Runtime Responsibility"]
        direction TB
        R1["Core API & Domain Logic"]
        R2["Agent Implementations"]
        R3["Domain Service Modules"]
        R4["Tool Implementations"]
        R5["MCP & Policy Gateway"]
        R6["Deployable Apps"]
        R7["Quality Benchmarks"]
        R8["Cloud Infrastructure"]
    end

    SRC --> R1
    AG --> R2
    SVC --> R3
    TOOLS --> R4
    MCP --> R5
    APPS --> R6
    EVAL_DIR --> R7
    INFRA --> R8
```

---

## 5. Data stores & data flow

What data lives where, and how it moves through the system.

```mermaid
flowchart LR
    subgraph inputs["Inputs"]
        ALERT_IN["Alert / Webhook"]
        DOCS["Runbooks · ADRs · Docs"]
        OBS_IN["Logs · Metrics · Traces"]
        CODE["Source Code · Deployments"]
    end

    subgraph processing["Processing"]
        API_P["API Service"]
        WORKER_P["Investigation Worker"]
        AGENT_P["Agents + Bedrock"]
        REDACT["Secrets Redaction"]
        GATE_P["Tool Gateway"]
    end

    subgraph stores["Persistent Stores"]
        PG_D[("PostgreSQL")]
        OS_D[("OpenSearch")]
        REDIS_D[("Redis")]
    end

    subgraph outputs["Outputs"]
        REPORT["RCA Report · Post-incident Report"]
        NOTIFY_OUT["Notifications"]
        ACTION["Controlled Remediation"]
        LEARN["RAG Re-index · Golden Dataset"]
    end

    ALERT_IN --> API_P --> PG_D
    API_P -->|"incident.opened"| WORKER_P

    WORKER_P --> AGENT_P
    AGENT_P --> REDACT
    REDACT --> GATE_P

    OBS_IN --> GATE_P
    CODE --> GATE_P
    DOCS -->|"ingest + embed"| OS_D

    GATE_P -->|"evidence items"| PG_D
    AGENT_P -->|"query"| OS_D
    AGENT_P -->|"RCA · decisions"| PG_D
    WORKER_P <-->|"workflow state"| REDIS_D

    PG_D --> REPORT --> NOTIFY_OUT
    AGENT_P --> ACTION
    PG_D --> LEARN --> OS_D
```

### Data ownership summary

| Store | Data | Retention |
|---|---|---|
| **PostgreSQL** | Incidents, evidence, RCA, approvals, audit logs, users/roles | Incident lifecycle + 90d audit minimum |
| **OpenSearch** | Document chunks, embeddings, retrieval metadata | Refreshed on re-index |
| **Redis** | Investigation workflow cache, session state, rate limit counters | Duration of investigation |
| **External** | Raw telemetry, source code | Not permanently stored in AEGIS |

---

## 6. Entity relationship model (conceptual)

Core domain entities in PostgreSQL.

```mermaid
erDiagram
    INCIDENT ||--o{ EVIDENCE : contains
    INCIDENT ||--o{ INVESTIGATION_STEP : has
    INCIDENT ||--o| RCA_REPORT : produces
    INCIDENT ||--o{ REMEDIATION : proposes
    INCIDENT ||--o{ NOTIFICATION : triggers
    INCIDENT }o--|| USER : assigned_to

    RCA_REPORT ||--o{ EVIDENCE : cites
    RCA_REPORT ||--o{ RCA_VERSION : amended_as

    REMEDIATION ||--o| APPROVAL_REQUEST : requires
    APPROVAL_REQUEST }o--|| USER : decided_by

    INVESTIGATION_STEP }o--|| AGENT : executed_by
    INVESTIGATION_STEP ||--o{ TOOL_INVOCATION : uses

    TOOL_INVOCATION ||--|| AUDIT_LOG : recorded_in
    AGENT ||--o{ TOOL_INVOCATION : invokes

    POLICY_RULE ||--o{ TOOL_INVOCATION : governs
    USER }o--|| ROLE : has

    INCIDENT {
        uuid id PK
        string state
        string severity
        string affected_service
        uuid owner_id FK
        timestamp created_at
        timestamp updated_at
    }

    EVIDENCE {
        uuid id PK
        uuid incident_id FK
        string source
        string content_ref
        jsonb metadata
        timestamp collected_at
    }

    RCA_REPORT {
        uuid id PK
        uuid incident_id FK
        string root_cause
        float confidence
        string status
        jsonb citations
    }

    REMEDIATION {
        uuid id PK
        uuid incident_id FK
        string action_class
        string status
        jsonb action_payload
    }

    APPROVAL_REQUEST {
        uuid id PK
        uuid remediation_id FK
        uuid approver_id FK
        string decision
        timestamp decided_at
        timestamp expires_at
    }

    AUDIT_LOG {
        uuid id PK
        string actor
        string action
        jsonb input
        jsonb output
        timestamp created_at
    }

    POLICY_RULE {
        uuid id PK
        string tool_name
        string action_class
        string scope
        boolean allowed
    }
```

---

## 7. End-to-end incident sequence

Complete flow from alert to resolution.

```mermaid
sequenceDiagram
    autonumber
    participant Alert as Alerting System
    participant API as AEGIS API
    participant PG as PostgreSQL
    participant EB as EventBridge
    participant SQS as SQS Queue
    participant Worker as Investigation Worker
    participant Cmd as Incident Commander
    participant Agents as Specialized Agents
    participant GW as Tool Gateway
    participant Ext as External Systems
    participant RAG as RAG / OpenSearch
    participant BR as Bedrock
    participant RCA as RCA Agent
    participant Eng as Engineer
    participant Approve as Approval Service

    Alert->>API: Webhook / incident signal
    API->>API: Validate · deduplicate
    API->>PG: Create incident (state=open)
    API->>EB: Publish incident.opened.v1
    API-->>Alert: 202 Accepted

    EB->>SQS: Route event
    SQS->>Worker: Deliver message
    Worker->>PG: Update state=investigating
    Worker->>Cmd: Start investigation plan

    loop Evidence collection
        Cmd->>Agents: Delegate task
        Agents->>GW: Tool call (read)
        GW->>GW: Policy check · auth
        GW->>Ext: Query logs / code / deploys
        Ext-->>GW: Raw data
        GW->>GW: Redact secrets
        GW-->>Agents: Evidence result
        Agents->>RAG: Retrieve runbooks / past incidents
        RAG->>BR: Embed query (if needed)
        RAG-->>Agents: Ranked chunks + citations
        Agents->>PG: Store evidence item
    end

    Cmd->>RCA: Synthesize evidence
    RCA->>BR: Generate RCA (structured)
    BR-->>RCA: RCA draft + confidence
    RCA->>PG: Store RCA report

    alt confidence >= threshold
        RCA->>Eng: Notify — RCA ready (FR-027)
        Eng->>API: Accept / amend RCA
        API->>PG: Update state=identified
    else confidence < threshold
        RCA->>Eng: Escalate — manual review (FR-028)
    end

    Note over Eng,Approve: Remediation phase (v0.9+)

    Eng->>API: Request remediation
    API->>GW: Propose action
    GW->>GW: Classify risk

    alt high-risk-write
        GW->>Approve: Create approval request (FR-057)
        Approve->>Eng: Notify approver (FR-029)
        Eng->>Approve: Approve / reject (FR-058)
        Approve->>PG: Record decision
    else destructive
        GW-->>Agents: DENY
    end

    GW->>Ext: Execute approved action
    GW->>PG: Audit log + state=remediating
    Worker->>Ext: Verify health / metrics
    Worker->>PG: Update state=resolved
    Worker->>RAG: Index post-incident report
```

---

## 8. Multi-agent orchestration

How agents collaborate under the Incident Commander.

```mermaid
flowchart TB
    START(["Incident Opened"]) --> CMD["Incident Commander<br/>(Plan investigation)"]

    CMD --> PLAN{"Investigation plan"}

    PLAN --> OBS["Observability Agent<br/>logs · metrics · traces · alarms"]
    PLAN --> CODE["Code Agent<br/>repo search · diffs · commits"]
    PLAN --> KNOW["Knowledge Agent<br/>runbooks · ADRs · past incidents"]
    PLAN --> DEPLOY["Deployment History<br/>recent deploys · config changes"]

    OBS --> GW["Tool Gateway"]
    CODE --> GW
    KNOW --> RAG["RAG Retrieval"]
    DEPLOY --> GW

    GW --> EXT_OBS["CloudWatch / Observability API"]
    GW --> EXT_GH["GitHub API"]
    RAG --> OS["OpenSearch"]

    OBS --> EVID_STORE[("Evidence Store<br/>(PostgreSQL)")]
    CODE --> EVID_STORE
    KNOW --> EVID_STORE
    DEPLOY --> EVID_STORE

    EVID_STORE --> CHECK{"Sufficient<br/>evidence?"}

    CHECK -->|"No"| CMD
    CHECK -->|"Yes"| RCA["RCA Agent<br/>(Synthesize + cite)"]
    CHECK -->|"Timeout / low confidence"| ESC["Escalate to Engineer"]

    RCA --> REVIEW{"Engineer review"}
    REVIEW -->|"Accepted"| IDENTIFIED["State: identified"]
    REVIEW -->|"Amended"| RCA
    REVIEW -->|"Rejected"| ESC

    IDENTIFIED --> REM["Remediation Agent<br/>(v0.9+)"]
    REM --> VERIFY["Verification Agent"]
    VERIFY --> RESOLVED(["State: resolved"])
```

---

## 9. Event-driven architecture

Async processing via EventBridge and SQS (ADR-003).

```mermaid
flowchart LR
    subgraph producers["Event Producers"]
        P1["API Service"]
        P2["Investigation Worker"]
        P3["RCA Agent"]
        P4["Tool Gateway"]
        P5["Approval Service"]
    end

    subgraph bus["Amazon EventBridge"]
        EBUS["aegis-events bus"]
    end

    subgraph queues["SQS Queues"]
        Q1["investigation-workflow"]
        Q2["notification"]
        Q3["rag-indexing"]
        Q4["evaluation"]
        DLQ["dead-letter-queue"]
    end

    subgraph consumers["Consumers"]
        C1["Investigation Worker"]
        C2["Notification Worker"]
        C3["RAG Indexer"]
        C4["Evaluation Runner"]
    end

    P1 -->|"incident.opened.v1"| EBUS
    P2 -->|"evidence.collected.v1"| EBUS
    P3 -->|"rca.completed.v1"| EBUS
    P4 -->|"remediation.executed.v1"| EBUS
    P5 -->|"remediation.approved.v1"| EBUS

    EBUS --> Q1 --> C1
    EBUS --> Q2 --> C2
    EBUS --> Q3 --> C3
    EBUS --> Q4 --> C4

    Q1 -.->|"max retries exceeded"| DLQ
    Q2 -.-> DLQ
    Q3 -.-> DLQ
```

### Event catalog (quick reference)

| Event | Queue | Consumer |
|---|---|---|
| `incident.opened.v1` | investigation-workflow | Investigation Worker |
| `evidence.collected.v1` | investigation-workflow | Investigation Worker |
| `rca.completed.v1` | notification | Notification Worker |
| `rca.escalated.v1` | notification | Notification Worker |
| `remediation.proposed.v1` | notification | Notification Worker |
| `incident.resolved.v1` | rag-indexing | RAG Indexer |
| `incident.closed.v1` | rag-indexing | RAG Indexer |

---

## 10. Tool gateway & security flow

Every external action passes through policy enforcement.

```mermaid
flowchart TB
    AGENT["Agent"] -->|"tool call request"| GW_IN["Tool Gateway"]

    subgraph gateway["Tool Gateway"]
        GW_IN --> AUTH["Authenticate agent identity"]
        AUTH --> CLASS["Classify action<br/>read · low-risk-write<br/>high-risk-write · destructive"]
        CLASS --> POLICY["Evaluate policy rules (FR-066/067)"]
        POLICY --> RATE["Rate limit check"]
        RATE --> DECIDE{"Decision"}
    end

    DECIDE -->|"destructive"| DENY["DENY — always blocked"]
    DECIDE -->|"high-risk-write"| APPROVAL{"Approved?"}
    DECIDE -->|"low-risk-write"| EXEC["Execute tool"]
    DECIDE -->|"read"| EXEC

    APPROVAL -->|"No"| PENDING["Pending approval request (FR-057)"]
    APPROVAL -->|"Yes"| EXEC

    EXEC --> REDACT["Redact secrets from response"]
    REDACT --> TOOL["External Tool<br/>CloudWatch · GitHub · CI/CD"]
    TOOL --> AUDIT["Append audit log (immutable)"]
    AUDIT --> RESP["Return result to agent"]

    DENY --> AUDIT
    PENDING --> NOTIFY["Notify approver (FR-029)"]

    subgraph stores["Persisted"]
        PG_AUDIT[("PostgreSQL<br/>audit_log · policy_rules · approvals")]
    end

    AUDIT --> PG_AUDIT
    PENDING --> PG_AUDIT
```

---

## 11. RAG pipeline

Knowledge ingestion, indexing, and retrieval.

```mermaid
flowchart LR
    subgraph sources["Knowledge Sources"]
        RB["Runbooks"]
        ADR["ADRs"]
        ARCH["Architecture Docs"]
        HIST["Historical Incidents"]
        CODE_D["Code Documentation"]
    end

    subgraph ingest["Ingestion Pipeline"]
        PARSE["Parse · Clean"]
        CHUNK["Chunk"]
        META["Extract Metadata<br/>(service · type · date)"]
        EMBED["Generate Embeddings<br/>(Bedrock Titan)"]
    end

    subgraph index["OpenSearch Index"]
        VEC["Vector Index"]
        FT["Full-text Index"]
    end

    subgraph retrieve["Retrieval (Hybrid)"]
        QUERY["Agent Query"]
        FILTER["Metadata Filter"]
        SEM["Semantic Search"]
        KW["Keyword Search"]
        RERANK["Merge · Rerank"]
        CITE["Attach Citations"]
    end

    subgraph consume["Consumption"]
        CTX["Context Assembly"]
        REDACT_R["Secrets Redaction"]
        LLM["Bedrock LLM"]
    end

    RB & ADR & ARCH & HIST & CODE_D --> PARSE --> CHUNK --> META --> EMBED
    EMBED --> VEC & FT

    QUERY --> FILTER --> SEM & KW
    VEC --> SEM
    FT --> KW
    SEM & KW --> RERANK --> CITE --> CTX --> REDACT_R --> LLM
```

---

## 12. AWS deployment topology (target)

Production infrastructure on AWS (v0.7+).

```mermaid
flowchart TB
    subgraph internet["Internet"]
        USER["Engineers"]
        ALERT_EXT["Alert Webhooks"]
    end

    subgraph aws["AWS Cloud — Single Region (eu-west-1)"]
        subgraph public["Public Subnet"]
            ALB["Application Load Balancer"]
        end

        subgraph private["Private Subnets"]
            subgraph ecs["ECS / Fargate"]
                API_T["API Task"]
                WORKER_T["Worker Task"]
            end

            RDS[("Amazon RDS<br/>PostgreSQL")]
            REDIS_AWS[("ElastiCache<br/>Redis")]
            OS_AWS[("Amazon OpenSearch")]
        end

        subgraph messaging_aws["Messaging"]
            EB_AWS["EventBridge"]
            SQS_AWS["SQS + DLQ"]
        end

        subgraph endpoints["VPC Endpoints"]
            VPCE_BR["Bedrock"]
            VPCE_S3["S3"]
            VPCE_SM["Secrets Manager"]
        end

        SM["Secrets Manager"]
        CW["CloudWatch<br/>Logs · Metrics · Alarms"]
        BR_AWS["Amazon Bedrock"]
        S3["S3<br/>Reports · Artifacts"]
    end

    subgraph external_aws["External"]
        GH_EXT["GitHub API"]
        OBS_EXT["Observability APIs"]
    end

    USER --> ALB --> API_T
    ALERT_EXT --> ALB --> API_T

    API_T --> RDS & REDIS_AWS & EB_AWS
    API_T --> OS_AWS
    EB_AWS --> SQS_AWS --> WORKER_T

    WORKER_T --> RDS & REDIS_AWS & OS_AWS
    WORKER_T --> VPCE_BR --> BR_AWS
    WORKER_T --> SM

    API_T --> CW
    WORKER_T --> CW
    API_T --> S3
    WORKER_T --> VPCE_S3 --> S3

    WORKER_T --> GH_EXT & OBS_EXT
```

---

## 13. Production simulator (dev/test)

Synthetic environment for development and evaluation.

```mermaid
flowchart TB
    subgraph simulator["Production Simulator (apps/simulator)"]
        US["User Service"]
        OS_S["Order Service"]
        PS["Payment Service"]
        IS["Inventory Service"]
        NS["Notification Service"]
    end

    subgraph outputs["Generated Signals"]
        LOGS["Application Logs"]
        METRICS["Metrics · Latency"]
        TRACES["Distributed Traces"]
        DEPLOYS["Deployment Events"]
    end

    subgraph scenarios["Failure Scenarios"]
        S1["DB Connection Exhaustion"]
        S2["Memory Leak"]
        S3["Latency Spike"]
        S4["Bad Deployment"]
        S5["Queue Backlog"]
        S6["Dependency Failure"]
    end

    subgraph aegis_dev["AEGIS (Dev / Test)"]
        API_D["API Service"]
        AGENTS_D["Agents"]
        EVAL_D["Evaluation Pipeline"]
        GOLD["Golden Dataset"]
    end

    US & OS_S & PS & IS & NS --> LOGS & METRICS & TRACES & DEPLOYS
    scenarios --> simulator

    LOGS & METRICS & TRACES & DEPLOYS -->|"incident signals"| API_D
    API_D --> AGENTS_D
    AGENTS_D --> EVAL_D
    EVAL_D --> GOLD
```

---

## 14. Complete platform map (single view)

High-level one-page reference tying everything together.

```mermaid
flowchart TB
    subgraph external_world["External World"]
        ACTORS["Engineers · SRE · Approvers"]
        ALERTS["Alerting · Observability · GitHub · CI/CD"]
    end

    subgraph platform["AEGIS PLATFORM"]
        direction TB

        subgraph entry["Entry Points"]
            API_E["REST API (FastAPI)"]
            WH_E["Webhooks"]
        end

        subgraph core["Core Services"]
            INC_S["Incident Service"]
            INV_S["Investigation Service"]
            APP_S["Approval Service"]
            NOT_S["Notification Service"]
        end

        subgraph ai_layer["AI Layer"]
            ORCH_E["LangGraph Orchestrator"]
            AGT_E["6 Specialized Agents"]
            RAG_E["RAG Pipeline"]
            BR_E["Bedrock LLM + Embeddings"]
        end

        subgraph security_layer["Security Layer"]
            GW_E["Tool Gateway + MCP"]
            POL_E["Policy Engine"]
            AUD_E["Audit Log"]
        end

        subgraph async_layer["Async Processing"]
            EB_E["EventBridge"]
            SQS_E["SQS + DLQ"]
            WRK_E["Investigation Worker"]
        end

        subgraph data_layer["Data Stores"]
            PG_E[("PostgreSQL")]
            OS_E[("OpenSearch")]
            RD_E[("Redis")]
        end
    end

    ACTORS <-->|"HTTPS + JWT"| API_E
    ALERTS --> WH_E --> API_E

    API_E --> INC_S & APP_S
    INC_S --> EB_E --> SQS_E --> WRK_E
    WRK_E --> INV_S --> ORCH_E --> AGT_E

    AGT_E --> GW_E --> POL_E
    GW_E --> ALERTS
    GW_E --> AUD_E --> PG_E

    AGT_E --> RAG_E --> OS_E
    AGT_E --> BR_E
    AGT_E --> PG_E

    INV_S --> NOT_S --> ACTORS
    APP_S --> ACTORS

    INC_S & INV_S & APP_S --> PG_E
    WRK_E <--> RD_E
```

---

## Related documents

- [System context (C4 Level 1)](context.md)
- [System boundaries](system-boundaries.md)
- [Incident flow](incident-flow.md)
- [Functional requirements](../requirements/functional-requirements.md)
- [Threat model](../security/threat-model.md)
- [ADR-001: Modular monolith](../adr/ADR-001-modular-monolith.md)
- [ADR-002: PostgreSQL](../adr/ADR-002-postgresql.md)
- [ADR-003: Event-driven investigation](../adr/ADR-003-event-driven-investigation.md)
- [ADR-004: AWS Bedrock](../adr/ADR-004-aws-bedrock.md)

---

## Diagram maintenance

Update this document when:

- A new ADR changes infrastructure or integration patterns
- New services or agents are added to the platform
- Database schema changes affect the entity model
- New external integrations are introduced

When updating diagrams, increment the **Last updated** date and reference the triggering ADR or requirement.
