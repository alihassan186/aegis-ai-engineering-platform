#!/usr/bin/env bash
# Start AEGIS local Postgres + pgAdmin + OpenSearch + Dashboards.
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

OS_PORT="${OPENSEARCH_HOST_PORT:-}"
if [[ -z "$OS_PORT" ]]; then
  OS_PORT="$(grep -E '^OPENSEARCH_HOST_PORT=' "$PROJECT_DIR/.env" | tail -n1 | cut -d= -f2- | tr -d '[:space:]' | tr -d '"' | tr -d "'")"
fi
OS_PORT="${OS_PORT:-9200}"

echo "Removing leftover AEGIS containers (avoids Compose 1.29 recreate bug)..."
docker rm -f aegis-postgres aegis-pgadmin aegis-opensearch aegis-opensearch-dashboards 2>/dev/null || true
docker ps -aq --filter name=aegis-postgres --filter name=aegis-pgadmin --filter name=aegis-opensearch | xargs -r docker rm -f

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
# Empty knowledge index only (FR-040 store). No documents. aegis-logs is not created.
if ! curl -sf "http://127.0.0.1:${OS_PORT}/aegis-knowledge" >/dev/null; then
  curl -sf -X PUT "http://127.0.0.1:${OS_PORT}/aegis-knowledge" \
    -H 'Content-Type: application/json' \
    -d '{"settings":{"number_of_shards":1,"number_of_replicas":0}}' >/dev/null
fi

echo
docker-compose -f "$COMPOSE_FILE" --project-directory "$PROJECT_DIR" ps
echo
echo "Postgres:    127.0.0.1:5434  (user/password/db: aegis)"
echo "pgAdmin:     http://127.0.0.1:5051  (admin@example.com / admin)"
echo "OpenSearch:  http://127.0.0.1:${OS_PORT}  (index aegis-knowledge, empty)"
echo "Dashboards:  http://127.0.0.1:5601  (no login; Dev Tools for _cat / _search)"
