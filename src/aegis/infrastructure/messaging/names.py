"""ADR-003 local names. Queue URLs are resolved at runtime — not stored in git."""

EVENT_BUS_NAME = "aegis-events"
INVESTIGATION_QUEUE_NAME = "investigation-workflow"
INVESTIGATION_DLQ_NAME = "investigation-workflow-dlq"
INVESTIGATION_RULE_NAME = "incident-opened-v1"
NOTIFICATION_QUEUE_NAME = "notification"
NOTIFICATION_DLQ_NAME = "notification-dlq"
NOTIFICATION_COMPLETED_RULE = "rca-completed-v1"
NOTIFICATION_ESCALATED_RULE = "rca-escalated-v1"
DEFAULT_REGION = "eu-west-1"
VISIBILITY_TIMEOUT_SECONDS = 300
MAX_RECEIVE_COUNT = 3
# rag-indexing / evaluation queues are named in ADR-003. Do not create consumers here.
