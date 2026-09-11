#!/usr/bin/env bash
# Start AEGIS local Postgres + pgAdmin + OpenSearch + Dashboards + LocalStack.
# Workaround: docker-compose 1.29 crashes with KeyError ContainerConfig
# when recreating containers on Docker Engine 24+. Always create fresh.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$ROOT/docker/docker-compose.yml"
PROJECT_DIR="$ROOT/docker"

if [[ ! -f "$PROJECT_DIR/.env" ]]; then
  cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
fi
if ! grep -q '^OPENSEARCH_HOST_PORT=' "$PROJECT_DIR/.env"; then
  printf '\nOPENSEARCH_HOST_PORT=9200\n' >> "$PROJECT_DIR/.env"
fi
if ! grep -q '^OPENSEARCH_DASHBOARDS_HOST_PORT=' "$PROJECT_DIR/.env"; then
  printf '\nOPENSEARCH_DASHBOARDS_HOST_PORT=5601\n' >> "$PROJECT_DIR/.env"
fi
if ! grep -q '^LOCALSTACK_HOST_PORT=' "$PROJECT_DIR/.env"; then
  printf '\nLOCALSTACK_HOST_PORT=4566\n' >> "$PROJECT_DIR/.env"
fi

OS_PORT="${OPENSEARCH_HOST_PORT:-}"
if [[ -z "$OS_PORT" ]]; then
  OS_PORT="$(grep -E '^OPENSEARCH_HOST_PORT=' "$PROJECT_DIR/.env" | tail -n1 | cut -d= -f2- | tr -d '[:space:]' | tr -d '"' | tr -d "'")"
fi
OS_PORT="${OS_PORT:-9200}"

LS_PORT="${LOCALSTACK_HOST_PORT:-}"
if [[ -z "$LS_PORT" ]]; then
  LS_PORT="$(grep -E '^LOCALSTACK_HOST_PORT=' "$PROJECT_DIR/.env" | tail -n1 | cut -d= -f2- | tr -d '[:space:]' | tr -d '"' | tr -d "'")"
fi
LS_PORT="${LS_PORT:-4566}"

echo "Removing leftover AEGIS containers (avoids Compose 1.29 recreate bug)..."
docker rm -f aegis-postgres aegis-pgadmin aegis-opensearch aegis-opensearch-dashboards aegis-localstack 2>/dev/null || true
docker ps -aq --filter name=aegis-postgres --filter name=aegis-pgadmin --filter name=aegis-opensearch --filter name=aegis-localstack | xargs -r docker rm -f

echo "Starting services..."
docker-compose -f "$COMPOSE_FILE" --project-directory "$PROJECT_DIR" up -d

echo "Waiting for OpenSearch on 127.0.0.1:${OS_PORT} ..."
for _ in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:${OS_PORT}/_cluster/health" >/dev/null; then
    break
  fi
  sleep 2
done
if ! curl -sf "http://127.0.0.1:${OS_PORT}/_cluster/health" >/dev/null; then
  echo "OpenSearch did not become healthy. If Linux reports max virtual memory: sudo sysctl -w vm.max_map_count=262144" >&2
  exit 1
fi
# Knowledge index (FR-043 mapping). No documents. aegis-logs is not created.
# An existing 3.1 empty index (no knn) is upgraded on ingest, not here.
MAPPINGS="$ROOT/src/aegis/infrastructure/rag/mappings.json"
if ! curl -sf "http://127.0.0.1:${OS_PORT}/aegis-knowledge" >/dev/null; then
  curl -sf -X PUT "http://127.0.0.1:${OS_PORT}/aegis-knowledge" \
    -H 'Content-Type: application/json' \
    --data-binary @"$MAPPINGS" >/dev/null
fi

echo "Waiting for LocalStack on 127.0.0.1:${LS_PORT} ..."
for _ in $(seq 1 40); do
  if curl -sf "http://127.0.0.1:${LS_PORT}/_localstack/health" | grep -Eq '"sqs"|"events"'; then
    break
  fi
  sleep 2
done
if ! curl -sf "http://127.0.0.1:${LS_PORT}/_localstack/health" | grep -Eq '"sqs"|"events"'; then
  echo "LocalStack did not become healthy on 127.0.0.1:${LS_PORT}" >&2
  exit 1
fi
bash "$ROOT/scripts/localstack-init.sh"

echo
docker-compose -f "$COMPOSE_FILE" --project-directory "$PROJECT_DIR" ps
echo
echo "Postgres:    127.0.0.1:5434  (user/password/db: aegis)"
echo "pgAdmin:     http://127.0.0.1:5051  (admin@example.com / admin)"
echo "OpenSearch:  http://127.0.0.1:${OS_PORT}  (index aegis-knowledge; ingest to fill)"
echo "Dashboards:  http://127.0.0.1:5601  (no login; Dev Tools for _cat / _search)"
echo "LocalStack:  http://127.0.0.1:${LS_PORT}  (bus aegis-events, queue investigation-workflow)"
