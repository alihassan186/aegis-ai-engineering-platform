# Risk Register

**Document owner:** Engineering  
**Status:** Draft  
**Last updated:** 2026-09-03

Tracks product, technical, operational, and security risks. Reviewed at each major release milestone.

**Rating:** Likelihood (L) and Impact (I) on scale 1–5. **Score** = L × I.

---

## Risk summary

| ID | Risk | Category | L | I | Score | Status | Mitigation |
|---|---|---|---|---|---|---|---|
| RISK-001 | LLM hallucination produces incorrect RCA | Technical | 4 | 5 | 20 | Open | Evidence citation requirement; human review; benchmark evaluation |
| RISK-002 | Agent executes unauthorized production action | Security | 3 | 5 | 15 | Open | Tool gateway; policy enforcement; least privilege; approval gates |
| RISK-003 | Prompt injection via retrieved documents | Security | 3 | 4 | 12 | Open | Input sanitization; treat RAG content as untrusted; output validation |
| RISK-004 | Bedrock API unavailability or throttling | Operational | 3 | 4 | 12 | Open | Retry with backoff; fallback model; queue-based async processing |
| RISK-005 | Investigation cost exceeds budget per incident | Financial | 3 | 3 | 9 | Open | Token tracking; model routing; caching; cost alerts |
| RISK-006 | Scope creep delays foundation delivery | Product | 4 | 3 | 12 | Open | Incremental roadmap; ADRs; phase gates |
| RISK-007 | Insufficient evaluation data for RCA benchmarking | Product | 3 | 4 | 12 | Partial v0.3 | Simulator + webhook ingest exist; golden RCA dataset still open |
| RISK-008 | Sensitive data leaked in logs or LLM context | Security | 3 | 5 | 15 | Open | PII/secrets redaction; context size limits; audit review |
| RISK-009 | Single-region AWS dependency | Operational | 2 | 4 | 8 | Accepted | Accept for v1.0; multi-region deferred |
| RISK-010 | Agent infinite loop or runaway token consumption | Technical | 3 | 3 | 9 | Open | Step limits; token budgets; timeout enforcement |
| RISK-011 | OpenSearch index corruption or data loss | Operational | 2 | 4 | 8 | Open | Automated snapshots; re-indexing pipeline |
| RISK-012 | Key person dependency (solo developer) | Operational | 4 | 3 | 12 | Open | Documentation; ADRs; conventional commits |
| RISK-013 | Over-engineering before validating core value | Product | 4 | 3 | 12 | Open | Modular monolith first; ADR-gated complexity |
| RISK-014 | GitHub API rate limiting during code search | Operational | 2 | 3 | 6 | Open | Caching; scoped queries; backoff |
| RISK-015 | Incorrect remediation causes production outage | Security | 2 | 5 | 10 | Open | Approval gates; verification agent; rollback support |

---

## Detailed risk descriptions

### RISK-001 — LLM hallucination produces incorrect RCA

**Description:** The RCA agent may confidently state an incorrect root cause not supported by collected evidence, leading engineers to pursue wrong remediation.

**Impact:** Extended incident duration, incorrect fixes, potential production harm.

**Mitigation:**
- Require evidence citations for every RCA claim (FR-031)
- Distinguish hypothesis from confirmed root cause (FR-033)
- Human acceptance/rejection workflow (FR-034)
- Golden dataset evaluation before release (FR-090, FR-091)
- Confidence scoring with escalation below threshold (FR-025)

**Owner:** Engineering  
**Review date:** v0.5 release gate

---

### RISK-002 — Agent executes unauthorized production action

**Description:** An agent or compromised tool path could modify production systems, deploy code, or delete resources without authorization.

**Impact:** Production outage, data loss, security breach.

**Mitigation:**
- Centralized tool gateway with policy enforcement (FR-060, FR-064)
- Action classification: read / low-risk / high-risk / destructive (FR-052)
- Human approval for high-risk and destructive actions (FR-053, NFR-037)
- Least-privilege IAM for agent service accounts (NFR-033, NFR-034)
- Immutable audit log (FR-100, NFR-038)

**Owner:** Security / Engineering  
**Review date:** v0.6 release gate

---

### RISK-003 — Prompt injection via retrieved documents

**Description:** Malicious or compromised content in runbooks, code comments, or incident records could inject instructions that manipulate agent behavior.

**Impact:** Unauthorized actions, data exfiltration, incorrect RCA.

**Mitigation:**
- Treat all retrieved content as untrusted data, not instructions (NFR-036)
- Separate system prompts from user/retrieved content
- Output validation and schema enforcement for structured responses
- Tool gateway authorization independent of LLM output
- Security tests for prompt injection scenarios

**Owner:** Security / Engineering  
**Review date:** v0.4 release gate

---

### RISK-007 — Insufficient evaluation data for RCA benchmarking

**Status:** Partial v0.3 — **not closed.**

**Description:** RCA quality (FR-090, FR-091) needs repeatable incidents and a labelled golden dataset. Without either, later agent evaluation has nothing fair to score.

**Impact:** Agents cannot be benchmarked; hallucination and retrieval quality stay unmeasured.

**v0.3 mitigation (done):**
- Production simulator (`apps/simulator/`) can activate a named scenario and emit a signed incident signal (FR-080–084).
- AEGIS webhook ingest + open-incident fingerprint (FR-113, FR-007) produce a stable `open` incident operators can GET and show in `/docs`.
- This removes the “no incidents exist to evaluate against” blocker for local work.

**Still open:**
- No **golden RCA dataset** (expected root cause, evidence, citations per scenario).
- Simulator signals are synthetic shape, not production telemetry.
- No eval harness, no FR-090/FR-091 scoring.

**Do not close** this risk until a golden dataset exists and is used at an investigation/eval gate (later phases).

**Owner:** Engineering  
**Review date:** investigation / evaluation gate (after v0.5 agents at the earliest)

---

### RISK-008 — Sensitive data leaked in logs or LLM context

**Description:** Logs, traces, or code retrieved during investigation may contain credentials, PII, or secrets that get sent to Bedrock or stored in audit logs.

**Impact:** Credential exposure, compliance violation, data breach.

**Mitigation:**
- Secrets detection and redaction before LLM context assembly
- Configurable data classification and exclusion rules
- Minimum necessary context principle for retrieval
- Encrypted storage and access-controlled audit logs (NFR-064)
- Regular audit log review process

**Owner:** Security  
**Review date:** v0.5 release gate

---

### RISK-015 — Incorrect remediation causes production outage

**Description:** An approved but incorrect remediation action (e.g., scaling down wrong service, bad config change) worsens the incident.

**Impact:** Extended outage, cascading failures.

**Mitigation:**
- Risk classification on all remediation recommendations (FR-051)
- Mandatory human approval for high-risk actions (FR-053)
- Verification agent checks post-remediation health (FR-055)
- Rollback recommendation on verification failure (FR-056)
- Canary deployment support (future)

**Owner:** Engineering  
**Review date:** v0.9 release gate

---

## Risk review process

1. Review all open risks at each version release gate
2. Add new risks when architecture or scope changes
3. Close risks when mitigations are implemented and verified
4. Escalate any risk with score ≥ 15 to explicit release blocker status

---

## Related documents

- [Threat model](../security/threat-model.md)
- [Non-functional requirements](non-functional-requirements.md)
- [SLOs and SLIs](slos-and-slis.md)
