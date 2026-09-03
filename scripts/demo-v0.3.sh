#!/usr/bin/env bash
# v0.3 operator demo: scenario → webhook → one open incident (FR-084, FR-113, FR-007).
#
# Prerequisites (this script does not start them):
#   - Postgres up and migrated:  uv run alembic upgrade head
#   - AEGIS on 127.0.0.1:8000:   uv run uvicorn aegis.main:app --host 127.0.0.1 --port 8000
#   - Simulator on 127.0.0.1:8001: uv run uvicorn apps.simulator.main:app --host 127.0.0.1 --port 8001
#   - Repo-root .env loaded by those processes (AEGIS_WEBHOOK_SECRET / SIMULATOR_WEBHOOK_SECRET,
#     AEGIS_JWT_SECRET, AEGIS_BASE_URL). Do not put secrets in this file.
#
# Usage (repo root):
#   bash scripts/demo-v0.3.sh

set -euo pipefail

AEGIS_URL="${AEGIS_URL:-http://127.0.0.1:8000}"
SIMULATOR_URL="${SIMULATOR_URL:-http://127.0.0.1:8001}"
SCENARIO="${SCENARIO:-latency_spike}"
EXPECTED_SERVICE="${EXPECTED_SERVICE:-payment}"

HTTP_CODE=""
HTTP_BODY=""

fail() {
  echo "demo-v0.3: $*" >&2
  exit 1
}

json_get() {
  python3 -c 'import json,sys; print(json.load(sys.stdin)'"$1"')'
}

http() {
  local method="$1"
  local url="$2"
  shift 2
  [[ -n "${HTTP_BODY:-}" && -f "${HTTP_BODY}" ]] && rm -f "$HTTP_BODY"
  HTTP_BODY="$(mktemp)"
  HTTP_CODE="$(curl -sS -X "$method" "$url" "$@" -o "$HTTP_BODY" -w '%{http_code}')"
}

cleanup() {
  [[ -n "${HTTP_BODY:-}" && -f "${HTTP_BODY}" ]] && rm -f "$HTTP_BODY"
}
trap cleanup EXIT

echo "Checking AEGIS health at ${AEGIS_URL}/health ..."
http GET "${AEGIS_URL}/health"
[[ "$HTTP_CODE" == "200" ]] || fail "AEGIS health HTTP ${HTTP_CODE}. Start AEGIS on port 8000 first."
[[ "$(json_get '["status"]' <"$HTTP_BODY")" == "ok" ]] || fail "AEGIS /health did not return status=ok."

echo "Checking simulator health at ${SIMULATOR_URL}/health ..."
http GET "${SIMULATOR_URL}/health"
[[ "$HTTP_CODE" == "200" ]] || fail "Simulator health HTTP ${HTTP_CODE}. Start the simulator on port 8001 first."
[[ "$(json_get '["status"]' <"$HTTP_BODY")" == "ok" ]] || fail "Simulator /health did not return status=ok."
[[ "$(json_get '.get("app","")' <"$HTTP_BODY")" == "simulator" ]] || fail "Port 8001 is not the simulator. Do not use AEGIS /docs on 8001."

echo "Activating scenario ${SCENARIO} ..."
http POST "${SIMULATOR_URL}/scenarios/${SCENARIO}"
if [[ "$HTTP_CODE" != "200" ]]; then
  cat "$HTTP_BODY" >&2
  fail "Activate scenario HTTP ${HTTP_CODE}."
fi

echo "First emit (expect 201 create) ..."
http POST "${SIMULATOR_URL}/emit"
if [[ "$HTTP_CODE" != "201" ]]; then
  cat "$HTTP_BODY" >&2
  err_code="$(json_get '.get("error",{}).get("code","")' <"$HTTP_BODY" 2>/dev/null || true)"
  if [[ "$HTTP_CODE" == "200" ]]; then
    fail "First emit HTTP 200, expected 201. An open ${EXPECTED_SERVICE}/${SCENARIO} incident already exists this UTC hour — close it or wait."
  fi
  if [[ "$err_code" == "AEGIS_NOT_CONFIGURED" ]]; then
    fail "Simulator has no AEGIS_BASE_URL. Add it to repo-root .env (see config/.env.example) and restart the simulator."
  fi
  if [[ "$err_code" == "WEBHOOK_NOT_CONFIGURED" ]]; then
    fail "Set SIMULATOR_WEBHOOK_SECRET (or AEGIS_WEBHOOK_SECRET) in .env to the same value AEGIS uses, then restart both processes."
  fi
  fail "First emit HTTP ${HTTP_CODE}, expected 201${err_code:+ (${err_code})}."
fi
first_id="$(json_get '["id"]' <"$HTTP_BODY")"
[[ -n "$first_id" && "$first_id" != "None" ]] || fail "First emit JSON had no id."

echo "Dev login (JWT is signed by AEGIS from AEGIS_JWT_SECRET; this script has no secret) ..."
http POST "${AEGIS_URL}/api/v1/auth/token" \
  -H 'Content-Type: application/json' \
  -d '{"username":"demo","role":"engineer"}'
if [[ "$HTTP_CODE" != "200" ]]; then
  cat "$HTTP_BODY" >&2
  fail "Dev token HTTP ${HTTP_CODE}."
fi
token="$(json_get '["access_token"]' <"$HTTP_BODY")"
[[ -n "$token" && "$token" != "None" ]] || fail "Token response had no access_token."

echo "GET ${AEGIS_URL}/api/v1/incidents/${first_id} ..."
http GET "${AEGIS_URL}/api/v1/incidents/${first_id}" \
  -H "Authorization: Bearer ${token}"
if [[ "$HTTP_CODE" != "200" ]]; then
  cat "$HTTP_BODY" >&2
  fail "GET incident HTTP ${HTTP_CODE}."
fi
got_id="$(json_get '["id"]' <"$HTTP_BODY")"
got_state="$(json_get '["state"]' <"$HTTP_BODY")"
got_service="$(json_get '["affected_service"]' <"$HTTP_BODY")"
[[ "$got_id" == "$first_id" ]] || fail "GET returned id ${got_id}, expected ${first_id}."
[[ "$got_state" == "open" ]] || fail "Incident ${first_id} state is ${got_state}, expected open."
[[ "$got_service" == "$EXPECTED_SERVICE" ]] || fail "Incident ${first_id} affected_service is ${got_service}, expected ${EXPECTED_SERVICE}."

echo "Second emit (expect 200 same id) ..."
http POST "${SIMULATOR_URL}/emit"
if [[ "$HTTP_CODE" != "200" ]]; then
  cat "$HTTP_BODY" >&2
  fail "Second emit HTTP ${HTTP_CODE}, expected 200."
fi
second_id="$(json_get '["id"]' <"$HTTP_BODY")"

echo
echo "first_id=${first_id}"
echo "second_id=${second_id}"
echo "docs=${AEGIS_URL}/docs  (then GET /api/v1/incidents/${first_id})"
if [[ "$first_id" != "$second_id" ]]; then
  fail "Duplicate emit created a different id (FR-007 failed)."
fi
echo "demo-v0.3: ok (one open incident, duplicate emit collapsed)"
