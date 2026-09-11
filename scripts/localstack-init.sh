#!/usr/bin/env bash
# Idempotent EventBridge bus + SQS + DLQ + rule (ADR-003).
# Runs awslocal inside aegis-localstack so `sudo bash scripts/docker-up.sh` works
# without root needing uv. Dummy creds only (test/test). Never real keys.
# rag-indexing / evaluation queues are named in ADR-003. Do not create them here.

set -euo pipefail

REGION="${AEGIS_AWS_REGION:-eu-west-1}"
BUS="${AEGIS_EVENT_BUS_NAME:-aegis-events}"
QUEUE="${AEGIS_INVESTIGATION_QUEUE_NAME:-investigation-workflow}"
DLQ="${QUEUE}-dlq"
RULE="incident-opened-v1"
SOURCE="aegis.incidents"
DETAIL_TYPE="incident.opened.v1"

if ! docker ps --format '{{.Names}}' 2>/dev/null | grep -qx aegis-localstack; then
  echo "aegis-localstack is not running. Start it with scripts/docker-up.sh" >&2
  exit 1
fi

aws_local() {
  docker exec \
    -e AWS_ACCESS_KEY_ID=test \
    -e AWS_SECRET_ACCESS_KEY=test \
    -e AWS_DEFAULT_REGION="$REGION" \
    aegis-localstack awslocal "$@"
}

# JSON --attributes maps. Do not use Key=Value shorthand: commas in
# RedrivePolicy / Policy values split the map.
json_queue_attrs() {
  python3 -c "
import json, sys
print(json.dumps({
    'VisibilityTimeout': '300',
    'RedrivePolicy': json.dumps({
        'deadLetterTargetArn': sys.argv[1],
        'maxReceiveCount': '3',
    }),
}))
" "$1"
}

json_queue_policy() {
  python3 -c "
import json, sys
print(json.dumps({
    'Policy': json.dumps({
        'Version': '2012-10-17',
        'Statement': [{
            'Sid': 'AllowEventBridgeSend',
            'Effect': 'Allow',
            'Principal': {'Service': 'events.amazonaws.com'},
            'Action': 'sqs:SendMessage',
            'Resource': sys.argv[1],
        }],
    }),
}))
" "$1"
}

echo "Provisioning LocalStack bus=${BUS} queue=${QUEUE} dlq=${DLQ} ..."

aws_local events create-event-bus --name "$BUS" >/dev/null 2>&1 || true

aws_local sqs create-queue --queue-name "$DLQ" >/dev/null 2>&1 || true
DLQ_URL="$(aws_local sqs get-queue-url --queue-name "$DLQ" --query QueueUrl --output text | tr -d '\r')"
DLQ_ARN="$(aws_local sqs get-queue-attributes --queue-url "$DLQ_URL" --attribute-names QueueArn --query Attributes.QueueArn --output text | tr -d '\r')"

aws_local sqs create-queue --queue-name "$QUEUE" >/dev/null 2>&1 || true
QUEUE_URL="$(aws_local sqs get-queue-url --queue-name "$QUEUE" --query QueueUrl --output text | tr -d '\r')"
QUEUE_ARN="$(aws_local sqs get-queue-attributes --queue-url "$QUEUE_URL" --attribute-names QueueArn --query Attributes.QueueArn --output text | tr -d '\r')"

aws_local sqs set-queue-attributes --queue-url "$QUEUE_URL" \
  --attributes "$(json_queue_attrs "$DLQ_ARN")" >/dev/null
aws_local sqs set-queue-attributes --queue-url "$QUEUE_URL" \
  --attributes "$(json_queue_policy "$QUEUE_ARN")" >/dev/null

PATTERN="$(python3 -c "import json; print(json.dumps({'source':['${SOURCE}'],'detail-type':['${DETAIL_TYPE}']}))")"
aws_local events put-rule \
  --name "$RULE" \
  --event-bus-name "$BUS" \
  --event-pattern "$PATTERN" >/dev/null

aws_local events put-targets \
  --event-bus-name "$BUS" \
  --rule "$RULE" \
  --targets "Id=investigation-sqs,Arn=${QUEUE_ARN}" >/dev/null

echo "LocalStack ready: bus=${BUS} queue=${QUEUE} (visibility 300s, maxReceive 3 → ${DLQ})"
