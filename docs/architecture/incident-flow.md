# Incident Flow

**Document owner:** Architecture  
**Status:** Draft  
**Last updated:** 2026-08-26

End-to-end lifecycle of an incident through AEGIS — from signal ingestion to resolution and knowledge capture.

---

## 1. Lifecycle overview

```text
  SIGNAL          INVESTIGATE         ANALYZE           REMEDIATE         LEARN
    │                 │                 │                 │                │
    ▼                 ▼                 ▼                 ▼                ▼
┌───────┐       ┌───────────┐     ┌──────────┐     ┌───────────┐    ┌─────────┐
│ Open  │──────▶│Investigating│───▶│Identified │────▶│Remediating│───▶│Resolved │
└───────┘       └───────────┘     └──────────┘     └───────────┘    └────┬────┘
    │                 │                 │                 │               │
    │                 │                 │                 │               ▼
    │                 │                 │                 │          ┌────────┐
    └─────────────────┴─────────────────┴─────────────────┴─────────▶│ Closed │
                                                                       └────────┘
```

| State | Description | Entry trigger |
|---|---|---|
| `open` | Incident created, not yet under investigation | Alert received or manual creation |
| `investigating` | Agents actively collecting evidence | Investigation workflow started |
| `identified` | Root cause analysis complete | RCA agent produces report |
| `remediating` | Approved remediation in progress | Human approves remediation plan |
| `resolved` | Remediation verified, incident fixed | Verification agent confirms resolution |
| `closed` | Post-incident review complete | Engineer closes incident |

---

## 2. Detailed flow

### Phase 1 — Signal ingestion

```text
Alert / Webhook / Manual
         │
         ▼
┌─────────────────────┐
│  Validate & parse   │
│  incident signal    │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Deduplicate        │──── duplicate ──▶ Link to existing incident
│  (same fingerprint) │
└──────────┬──────────┘
           │ new incident
           ▼
┌─────────────────────┐
│  Create incident    │
│  state = open       │
└──────────┬──────────┘
           │
           ▼
┌─────────────────────┐
│  Publish event:     │
│  incident.opened.v1 │
└─────────────────────┘
```

**Outputs:** Incident record, `incident.opened.v1` event on EventBridge/SQS.

---

### Phase 2 — Investigation orchestration

```text
incident.opened.v1
         │
         ▼
┌─────────────────────────┐
│  Investigation worker  │
│  picks up message      │
└──────────┬──────────────┘
           │
           ▼
┌─────────────────────────┐
│  Incident Commander     │
│  agent: plan investigation│
│  - identify affected svc │
│  - select evidence sources│
│  - delegate to agents    │
└──────────┬──────────────┘
           │
     ┌─────┼─────┬─────────────┐
     ▼     ▼     ▼             ▼
┌────────┐ ┌────────┐ ┌──────────┐ ┌──────────┐
│Observ. │ │ Code   │ │Knowledge │ │Deployment│
│ Agent  │ │ Agent  │ │ Agent    │ │ history  │
└───┬────┘ └───┬────┘ └────┬─────┘ └────┬─────┘
    │          │           │            │
    └──────────┴─────┬─────┴────────────┘
                     ▼
           ┌─────────────────┐
           │ Evidence store  │
           │ (linked to inc.)│
           └─────────────────┘
```

**State transition:** `open` → `investigating`

Each agent invocation:
1. Receives scoped task from orchestrator
2. Calls tools through gateway (read-only in this phase)
3. Returns structured evidence items
4. Evidence persisted and linked to incident

**Escalation triggers:**
- Agent failure after max retries
- Confidence below threshold
- Investigation duration exceeds limit
- Human requests pause

---

### Phase 3 — Root cause analysis

```text
Evidence collection complete
         │
         ▼
┌─────────────────────────┐
│  RCA Agent              │
│  - review all evidence  │
│  - cite sources         │
│  - identify root cause  │
│  - assess confidence    │
└──────────┬──────────────┘
           │
     ┌─────┴──────┐
     ▼            ▼
 confidence    confidence
  ≥ threshold   < threshold
     │            │
     ▼            ▼
┌─────────┐  ┌──────────────┐
│ RCA     │  │ Escalate to  │
│ report  │  │ human engineer│
└────┬────┘  └──────────────┘
     │
     ▼
┌─────────────────────────┐
│  Engineer review        │
│  accept / reject / amend│
└──────────┬──────────────┘
           │
           ▼
    state = identified
```

**RCA report structure:**

```json
{
  "incident_id": "...",
  "summary": "...",
  "root_cause": "...",
  "contributing_factors": ["..."],
  "confidence": 0.85,
  "status": "confirmed | hypothesis",
  "evidence_citations": [
    { "evidence_id": "...", "source": "...", "relevance": "..." }
  ],
  "recommended_actions": ["..."]
}
```

---

### Phase 4 — Remediation (v0.9+)

```text
RCA accepted
         │
         ▼
┌─────────────────────────┐
│  Remediation Agent      │
│  - propose actions      │
│  - classify risk level  │
└──────────┬──────────────┘
           │
     ┌─────┼──────────┬──────────────┐
     ▼     ▼          ▼              ▼
   read  low-risk   high-risk    destructive
     │   write        │              │
     │     │          ▼              ▼
     │     │    ┌──────────┐   ┌──────────┐
     │     │    │  Human   │   │  DENY    │
     │     │    │ approval │   │ (always) │
     │     │    └────┬─────┘   └──────────┘
     │     │         │ approved
     └─────┴─────────┘
           │
           ▼
┌─────────────────────────┐
│  Tool gateway executes  │
│  approved action        │
└──────────┬──────────────┘
           │
           ▼
    state = remediating
```

---

### Phase 5 — Verification

```text
Remediation executed
         │
         ▼
┌─────────────────────────┐
│  Verification Agent     │
│  - check service health │
│  - compare metrics      │
│  - confirm alarm cleared│
└──────────┬──────────────┘
           │
     ┌─────┴──────┐
     ▼            ▼
  resolved     failed
     │            │
     ▼            ▼
┌─────────┐  ┌──────────────┐
│ state = │  │ Recommend    │
│resolved │  │ rollback or  │
└────┬────┘  │ escalate     │
     │       └──────────────┘
     ▼
Post-incident report generated
```

---

### Phase 6 — Learning loop

```text
Incident closed
         │
         ▼
┌─────────────────────────┐
│  Post-incident report   │
│  - timeline             │
│  - evidence summary     │
│  - RCA                  │
│  - actions taken        │
│  - outcome              │
└──────────┬──────────────┘
           │
     ┌─────┴──────────────┐
     ▼                    ▼
┌──────────────┐   ┌─────────────────┐
│ Index in RAG │   │ Update golden   │
│ (historical  │   │ dataset (if     │
│  incidents)  │   │ validated)      │
└──────────────┘   └─────────────────┘
```

---

## 3. Event catalog

| Event | Publisher | Consumer | Schema version |
|---|---|---|---|
| `incident.opened` | API / webhook handler | Investigation worker | v1 |
| `incident.investigating` | Investigation worker | Audit, metrics | v1 |
| `evidence.collected` | Agent runtime | Evidence store, audit | v1 |
| `rca.completed` | RCA agent | API notification, audit | v1 |
| `rca.escalated` | RCA agent | Paging notification | v1 |
| `remediation.proposed` | Remediation agent | Approval workflow | v1 |
| `remediation.approved` | Approval handler | Tool gateway | v1 |
| `remediation.executed` | Tool gateway | Verification agent, audit | v1 |
| `incident.resolved` | Verification agent | RAG indexer, metrics | v1 |
| `incident.closed` | API (engineer) | Learning pipeline | v1 |

---

## 4. Failure handling

| Failure point | Behavior |
|---|---|
| SQS message processing fails | Retry up to 3 times with exponential backoff; then DLQ |
| Agent tool call fails | Retry tool once; if persistent, mark step failed and continue or escalate |
| Bedrock timeout | Retry with backoff; if persistent, escalate to human |
| RCA confidence too low | Escalate to human; do not auto-advance state |
| Remediation verification fails | Recommend rollback; notify engineer; remain in `remediating` |
| Duplicate event delivery | Idempotent handlers keyed by `incident_id` + event type |

---

## 5. Timing expectations

| Phase | Target duration | Escalation if exceeded |
|---|---|---|
| Signal → investigation start | < 5 seconds | Alert on queue lag |
| Evidence collection | < 5 minutes | Escalate to human |
| RCA generation | < 2 minutes | Escalate to human |
| Human approval (remediation) | Human-dependent | Reminder notification at 15 minutes |
| Verification | < 3 minutes | Escalate to human |

---

## Related documents

- [System context](context.md)
- [System boundaries](system-boundaries.md)
- [Functional requirements](../requirements/functional-requirements.md)
- [ADR-003: Event-driven investigation](../adr/ADR-003-event-driven-investigation.md)
