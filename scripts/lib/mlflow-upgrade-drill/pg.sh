# mlflow-upgrade-drill, container `pg` (postgres:17-alpine). Restores the global roles plus the `mlflow` database's
# section of the NEWEST core dump (/backup/pg, mounted read-only) into a scratch Postgres that listens on 127.0.0.1
# only, with trust auth (nothing outside this pod can reach it). Then it tells the `mlflow` container to go and waits
# for it to finish. Prints `restore errors: N` and `counts-before: ...`.
set -eu
TABLES="experiments runs registered_models model_versions metrics params endpoints secrets guardrails budget_policies"
# shellcheck disable=SC2012  # newest by mtime; the names are fixed (weyland-all-<date>.sql.gz), as in pg-restore-drill.sh
D=$(ls -1t /backup/pg/weyland-all-*.sql.gz | head -1)
echo "dump: $(basename "$D")"
mkdir -p /tmp/pg && initdb -D /tmp/pg -U postgres --auth=trust >/dev/null 2>&1
pg_ctl -D /tmp/pg -o "-k /tmp -c listen_addresses=127.0.0.1" -w start >/dev/null
zcat "$D" | awk '
  BEGIN { g = 1 }
  /^-- Databases/ { g = 0 }
  g { print; next }
  /^-- Database "mlflow" dump/ { m = 1 }
  m && /^-- Database "/ && !/"mlflow"/ { m = 0 }
  m { print }
' > /tmp/db.sql
echo "extracted: $(wc -l < /tmp/db.sql) lines"
psql -h /tmp -U postgres -q -f /tmp/db.sql >/dev/null 2>/tmp/err || true
echo "restore errors: $(grep -c ERROR /tmp/err || true)"
grep ERROR /tmp/err | head -5 || true
counts() {
  for t in $TABLES; do
    printf '%s=%s ' "$t" "$(psql -h /tmp -U postgres -d mlflow -tAc "select count(*) from $t" 2>/dev/null || echo MISSING)"
  done
}
echo "alembic-before: $(psql -h /tmp -U postgres -d mlflow -tAc 'select version_num from alembic_version' 2>/dev/null || echo MISSING)"
echo "counts-before: $(counts)"
touch /shared/ready
i=0
while [ ! -f /shared/done ] && [ "$i" -lt 1200 ]; do sleep 1; i=$((i + 1)); done
echo "alembic-after: $(psql -h /tmp -U postgres -d mlflow -tAc 'select version_num from alembic_version' 2>/dev/null || echo MISSING)"
echo "counts-after: $(counts)"
pg_ctl -D /tmp/pg -w stop >/dev/null
