#!/usr/bin/env bash
set -euo pipefail

ADMIN_URL="${APISIX_ADMIN_URL:-http://localhost:9180}"
ADMIN_KEY="${APISIX_ADMIN_KEY:?APISIX_ADMIN_KEY must be set (see .env)}"
UPSTREAM_HOST="${TOOL_SERVER_HOST:-weyland-tool-server.weyland.svc.cluster.local}"
UPSTREAM_PORT="${TOOL_SERVER_PORT:-8080}"

wait_for_apisix() {
  echo "Waiting for APISIX admin API..."
  for i in $(seq 1 30); do
    if curl -sf -o /dev/null "${ADMIN_URL}/apisix/admin/routes" \
        -H "X-API-KEY: ${ADMIN_KEY}"; then
      echo "APISIX ready."
      return 0
    fi
    sleep 2
  done
  echo "ERROR: APISIX admin API did not become ready." >&2
  exit 1
}

put_upstream() {
  local id="$1" name="$2"
  curl -sf -X PUT "${ADMIN_URL}/apisix/admin/upstreams/${id}" \
    -H "X-API-KEY: ${ADMIN_KEY}" \
    -H "Content-Type: application/json" \
    -d "{
      \"name\": \"${name}\",
      \"type\": \"roundrobin\",
      \"nodes\": {
        \"${UPSTREAM_HOST}:${UPSTREAM_PORT}\": 1
      }
    }"
}

put_route() {
  local id="$1" name="$2" prefix="$3" upstream_id="$4"
  curl -sf -X PUT "${ADMIN_URL}/apisix/admin/routes/${id}" \
    -H "X-API-KEY: ${ADMIN_KEY}" \
    -H "Content-Type: application/json" \
    -d "{
      \"name\": \"${name}\",
      \"uri\": \"${prefix}/*\",
      \"upstream_id\": \"${upstream_id}\",
      \"plugins\": {
        \"prometheus\": {}
      }
    }"
}

wait_for_apisix

echo "Seeding upstream..."
put_upstream "1" "weyland-tool-server"

echo "Seeding routes..."
put_route "1" "context"  "/context"  "1"
put_route "2" "pipeline" "/pipeline" "1"
put_route "3" "qdrant"   "/qdrant"   "1"
put_route "4" "weaviate" "/weaviate" "1"
put_route "5" "neo4j"    "/neo4j"    "1"

echo "Routes initialized."
