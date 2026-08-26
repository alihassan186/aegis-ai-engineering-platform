# ADR-004: Use Amazon Bedrock as the Primary LLM Provider

**Status:** Accepted  
**Date:** 2026-08-26  
**Deciders:** Engineering  
**Related:** [Threat model](../security/threat-model.md), [NFR-034](../requirements/non-functional-requirements.md)

---

## Context

AEGIS requires LLM capabilities for:

- Agent reasoning and orchestration decisions
- Root cause analysis synthesis from evidence
- Remediation recommendation generation
- Text embeddings for RAG retrieval
- Structured output parsing (RCA reports, evidence summaries)

The platform targets AWS deployment. The team is learning AWS GenAI services as part of the project objectives. Model selection, cost, latency, and security constraints must be evaluated.

---

## Problem

Which LLM provider and model access pattern should AEGIS use for agent reasoning, RCA generation, and embeddings?

Requirements:
- Production-grade API with SLA
- Structured output support (JSON mode)
- Embedding model for RAG
- Data not used for model training
- IAM-based authentication (no API keys in code)
- Cost tracking per investigation
- Region availability (eu-west-1 preferred for Ireland-based deployment)

---

## Decision

Use **Amazon Bedrock** as the primary LLM provider for all agent inference and embedding generation.

**Initial model selection:**

| Use case | Model | Rationale |
|---|---|---|
| Agent reasoning / RCA | `anthropic.claude-3-5-sonnet-20241022-v2:0` | Strong reasoning, structured output, tool use |
| Simple classification / routing | `anthropic.claude-3-haiku-20240307-v1:0` | Lower cost for low-complexity tasks |
| Embeddings (RAG) | `amazon.titan-embed-text-v2:0` | Native AWS embedding model, cost-effective |

**Access pattern:**
- Bedrock Runtime API via `boto3` (no HTTP API keys)
- VPC endpoint for Bedrock (no public internet for LLM calls in production)
- IAM role attached to ECS task — least privilege (`bedrock:InvokeModel` only)
- LLM credentials never passed to agent prompts or stored in database

**Structured outputs:**
- RCA reports, evidence summaries, and remediation recommendations use Pydantic schema enforcement
- Claude tool use for agent tool calling (via LangGraph tool nodes)

---

## Alternatives considered

### Alternative 1: OpenAI API (GPT-4o)

**Rejected because:**
- API key authentication — violates NFR-034 (no raw credentials in application)
- Data processing terms require careful review for operational data
- Not AWS-native — adds external network dependency and data egress
- Learning objective focuses on AWS GenAI stack
- Cost tracking requires custom implementation

### Alternative 2: Self-hosted open-source models (Llama, Mistral on EC2/GPU)

**Rejected because:**
- High operational overhead (GPU instance management, model loading, scaling)
- Inference latency and quality less predictable than managed service
- Cost at low volume is higher than Bedrock on-demand
- Appropriate for v2.0+ if cost optimization at scale requires it

### Alternative 3: Amazon SageMaker hosted endpoints

**Rejected because:**
- Requires model deployment and endpoint management
- Better suited for fine-tuned custom models (not needed in v0.x)
- Bedrock provides the same models without endpoint management overhead
- May revisit if custom fine-tuned model is required (v2.0+)

### Alternative 4: Multi-provider routing (Bedrock + OpenAI fallback)

**Deferred to v1.0+**

Considered for resilience but adds complexity. Bedrock multi-region failover is the first resilience pattern to implement.

---

## Trade-offs

| Benefit | Cost |
|---|---|
| IAM authentication — no API keys | AWS vendor lock-in |
| Data not used for model training (AWS policy) | Model selection limited to Bedrock catalog |
| VPC endpoint — no public internet | VPC endpoint cost (~$7/month per endpoint) |
| Pay-per-token — no idle cost | Token costs can accumulate for long investigations |
| Native CloudWatch integration for monitoring | Claude model availability varies by region |
| Consistent with AWS CDK infrastructure | Bedrock quotas require proactive management |

---

## Consequences

### Positive

- No API keys in code, environment, or LLM context (NFR-034 satisfied)
- IAM role per ECS task — auditable, rotatable, least privilege
- CloudWatch metrics for invocation count, latency, and errors (SLI-008)
- Token usage trackable per investigation for cost attribution (NFR-070)
- Claude tool use integrates naturally with LangGraph agent architecture

### Negative

- Bedrock quotas (TPM/RPM) may throttle concurrent investigations — request quota increases proactively
- Model availability in `eu-west-1` must be verified before deployment
- Bedrock latency (1–5 seconds per call) is a significant fraction of investigation duration
- Switching models requires code change and evaluation re-run

### Cost management rules

1. Track input/output tokens per investigation in audit log
2. Route low-complexity tasks (classification, routing) to Haiku
3. Set maximum token budget per investigation step (default: 4,000 output tokens)
4. Set maximum investigation step count (default: 20 steps) to prevent runaway costs
5. Alert when investigation cost exceeds configurable threshold (default: $0.50)

### Security rules

1. LLM prompts must not contain: raw credentials, full database connection strings, unredacted secrets
2. Secrets redaction pipeline runs before context assembly (see THR-009)
3. Bedrock invocation logged with: model_id, input_token_count, output_token_count, incident_id, agent_id
4. Bedrock Guardrails evaluated for v0.6+ (content filtering, denied topics)

### Model upgrade process

When upgrading model versions:
1. Run golden dataset evaluation (SLI-010) against new model
2. Compare RCA accuracy, latency, and cost against baseline
3. Require ≥ baseline accuracy before promoting to production
4. Document model change in ADR or release notes

---

## Related documents

- [Threat model — THR-009, THR-012](../security/threat-model.md)
- [Risk register — RISK-001, RISK-004, RISK-005](../requirements/risk-register.md)
- [NFR-034, NFR-045](../requirements/non-functional-requirements.md)
- [ADR-001: Modular monolith](ADR-001-modular-monolith.md)
