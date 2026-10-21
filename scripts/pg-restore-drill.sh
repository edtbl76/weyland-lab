#!/usr/bin/env bash
# Non-destructive restore drill for the core Postgres dump (docs/dr.md Postgres — weyland core; first run 2026-10-21).
#
# The nightly `postgres-backup` CronJob writes `pg_dumpall` of weyland-postgres to mother's USB disk
# (/mnt/minio/backups/pg/weyland-all-<date>.sql.gz). Until 2026-10-21 nothing had ever restored one. This starts a
# throwaway pod on mother with that directory mounted READ-ONLY and no Istio sidecar, runs a scratch Postgres inside it,
# restores the global roles plus ONE database's section from the newest dump, and prints the row counts of the tables
# you name. Nothing touches the live database: compare the counts with it yourself (the runbook line in dr.md).
#
#   usage: scripts/pg-restore-drill.sh <database> <table>...
#   e.g.   scripts/pg-restore-drill.sh mlflow experiments runs registered_models model_versions
# EXIT: 0 the pod ran and restored with 0 errors · 1 the restore reported errors or a table is missing · 2 could not run
set -euo pipefail

DB="${1:-}"; shift || true
[ -n "$DB" ] && [ "$#" -gt 0 ] || { echo "usage: $0 <database> <table>..." >&2; exit 2; }
case "$DB" in *[!a-z0-9_]*) echo "database name must be [a-z0-9_]: $DB" >&2; exit 2;; esac
for t in "$@"; do case "$t" in *[!a-z0-9_]*) echo "table name must be [a-z0-9_]: $t" >&2; exit 2;; esac; done

NS=weyland
POD=pg-restore-drill
CM=pg-restore-drill-script
WORK="$(mktemp -d)"
trap 'rm -rf "$WORK"; kubectl -n "$NS" delete pod "$POD" --ignore-not-found >/dev/null 2>&1 || true; kubectl -n "$NS" delete configmap "$CM" --ignore-not-found >/dev/null 2>&1 || true' EXIT

cat > "$WORK/drill.sh" <<EOF
set -eu
D=\$(ls -1t /backup/pg/weyland-all-*.sql.gz | head -1)
echo "dump: \$(basename "\$D")"
mkdir -p /tmp/pg && initdb -D /tmp/pg -U postgres >/dev/null 2>&1
pg_ctl -D /tmp/pg -o "-k /tmp -c listen_addresses=''" -w start >/dev/null
# globals (roles) up to "-- Databases", then only this database's section
zcat "\$D" | awk '
  BEGIN { g = 1 }
  /^-- Databases/ { g = 0 }
  g { print; next }
  /^-- Database "$DB" dump/ { m = 1 }
  m && /^-- Database "/ && !/"$DB"/ { m = 0 }
  m { print }
' > /tmp/db.sql
echo "extracted: \$(wc -l < /tmp/db.sql) lines"
psql -h /tmp -U postgres -q -f /tmp/db.sql >/dev/null 2>/tmp/err || true
echo "restore errors: \$(grep -c ERROR /tmp/err || true)"
grep ERROR /tmp/err | head -5 || true
for t in $*; do
  printf '%s=%s ' "\$t" "\$(psql -h /tmp -U postgres -d $DB -tAc "select count(*) from \$t" 2>/dev/null || echo MISSING)"
done; echo
pg_ctl -D /tmp/pg -w stop >/dev/null
EOF

kubectl -n "$NS" delete pod "$POD" --ignore-not-found >/dev/null
kubectl -n "$NS" delete configmap "$CM" --ignore-not-found >/dev/null
kubectl -n "$NS" create configmap "$CM" --from-file=drill.sh="$WORK/drill.sh" >/dev/null
kubectl -n "$NS" run "$POD" --restart=Never --image=postgres:17-alpine --overrides='{"metadata":{"labels":{"sidecar.istio.io/inject":"false"}},"spec":{"nodeName":"mother","automountServiceAccountToken":false,"securityContext":{"runAsUser":70,"runAsGroup":70},"containers":[{"name":"drill","image":"postgres:17-alpine","command":["sh","/drill/drill.sh"],"resources":{"requests":{"memory":"256Mi","cpu":"250m"},"limits":{"memory":"2Gi"}},"volumeMounts":[{"name":"b","mountPath":"/backup","readOnly":true},{"name":"s","mountPath":"/drill","readOnly":true}]}],"volumes":[{"name":"b","hostPath":{"path":"/mnt/minio/backups","type":"Directory"}},{"name":"s","configMap":{"name":"pg-restore-drill-script"}}]}}' >/dev/null

echo "→ restoring $DB from the newest dump (streams ~2 GB; ~10 min)…"
for _ in $(seq 1 120); do
  phase="$(kubectl -n "$NS" get pod "$POD" -o jsonpath='{.status.phase}' 2>/dev/null || true)"
  case "$phase" in Succeeded|Failed) break;; esac
  sleep 15
done
out="$(kubectl -n "$NS" logs "$POD" 2>/dev/null | grep -v -i 'locale\|initdb' || true)"
printf '%s\n' "$out"
[ "${phase:-}" = Succeeded ] || { echo "NOT A PASS: the drill pod ended in phase '${phase:-unknown}'" >&2; exit 2; }
[ -n "$out" ] || { echo "NOT A PASS: the drill printed nothing" >&2; exit 2; }
if ! grep -q '^restore errors: 0$' <<<"$out" || grep -q 'MISSING' <<<"$out"; then
  echo "RESTORE PROBLEM: errors above, or a table missing" >&2; exit 1
fi
echo "restore OK — compare the counts above with the live database"
