#!/usr/bin/env bash
# langfuse-context-tokens.sh — input tokens per LLM call, by trace name and model, from Langfuse (B255, 2026-11-20).
# Shows how big each AI surface's context is in real requests (operator, Realm, tool-server RAG, ...).
# Reads Langfuse's ClickHouse tables; prints token counts only. The ClickHouse password is read from the cluster
# Secret into a variable and never printed. Usage: langfuse-context-tokens.sh [days, default 7]
# Runbook: docs/runbooks/langfuse.md § Context size per surface.
set -euo pipefail
DAYS="${1:-7}"
case "$DAYS" in ''|*[!0-9]*) echo "usage: langfuse-context-tokens.sh [days]" >&2; exit 2 ;; esac
CHP="$(kubectl -n data-mesh get secret clickhouse-users -o jsonpath='{.data.weyland-users\.xml}' | base64 -d | grep -oP '(?<=<password>)[^<]+')"
[ -n "$CHP" ] || { echo "could not read the ClickHouse password from data-mesh/clickhouse-users" >&2; exit 2; }
kubectl -n data-mesh exec -i deploy/clickhouse -- clickhouse-client --user default --password "$CHP" \
  --format PrettyCompactMonoBlock --query "
SELECT t.name AS trace, o.provided_model_name AS model, count() AS calls,
       round(avg(o.usage_details['input'])) AS avg_in,
       round(quantile(0.95)(o.usage_details['input'])) AS p95_in,
       max(o.usage_details['input']) AS max_in
FROM langfuse.observations o FINAL
LEFT JOIN (SELECT id, any(name) AS name FROM langfuse.traces
           WHERE timestamp > now() - INTERVAL ${DAYS} DAY GROUP BY id) t ON t.id = o.trace_id
WHERE o.type = 'GENERATION' AND o.start_time > now() - INTERVAL ${DAYS} DAY AND o.usage_details['input'] > 0
GROUP BY trace, model ORDER BY calls DESC LIMIT 30"
