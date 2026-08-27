#!/usr/bin/env bash
# Start AEGIS local Postgres + pgAdmin.
# Workaround: docker-compose 1.29 crashes with KeyError ContainerConfig
# when recreating containers on Docker Engine 24+. Always create fresh.

set -euo pipefail

ROOT="$(cd "$(dirname "$0")/.." && pwd)"
COMPOSE_FILE="$ROOT/docker/docker-compose.yml"
PROJECT_DIR="$ROOT/docker"

if [[ ! -f "$PROJECT_DIR/.env" ]]; then
  cp "$PROJECT_DIR/.env.example" "$PROJECT_DIR/.env"
fi

echo "Removing leftover AEGIS containers (avoids Compose 1.29 recreate bug)..."
docker rm -f aegis-postgres aegis-pgadmin 2>/dev/null || true
docker ps -aq --filter name=aegis-postgres --filter name=aegis-pgadmin | xargs -r docker rm -f

echo "Starting services..."
docker-compose -f "$COMPOSE_FILE" --project-directory "$PROJECT_DIR" up -d

echo
docker-compose -f "$COMPOSE_FILE" --project-directory "$PROJECT_DIR" ps
echo
echo "Postgres: 127.0.0.1:5434  (user/password/db: aegis)"
echo "pgAdmin:  http://127.0.0.1:5051  (admin@example.com / admin)"
