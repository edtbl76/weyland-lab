#!/usr/bin/env bash
# MLflow upgrade drill (B227 follow-on, 2026-10-24) — prove an MLflow image's DB migration on a RESTORED COPY of the
# real `mlflow` database before that image touches the live one. MLflow's migrations are forward-only: a bad upgrade on
# the live DB is a restore (runbooks/mlflow.md), so the copy goes first.
#
# A throwaway pod on mother with two containers sharing localhost and an emptyDir:
#   pg      postgres:17-alpine — restores the roles + the `mlflow` section of the NEWEST core dump (/mnt/minio/backups/pg,
#           mounted READ-ONLY) into a scratch Postgres on 127.0.0.1 only; counts the key tables before and after.
#   mlflow  the image under test — runs the real `mlflow db upgrade` on that copy (timed), starts the server on it, and
#           asks /health and the AI Gateway's endpoint list (read from that database).
# No Istio sidecar, no service-account token, no MinIO, no network listener: nothing reaches the live database or
# leaves the pod. Same pattern as scripts/pg-restore-drill.sh. The container scripts: scripts/lib/mlflow-upgrade-drill/.
#
#   usage: scripts/mlflow-upgrade-drill.sh <image>
#   e.g.   scripts/mlflow-upgrade-drill.sh registry.weyland.lab/weyland-mlflow:git-<sha>
# EXIT: 0 PASS · 1 the drill ran and found a problem (named) · 2 could not run / nothing to judge
set -euo pipefail

NS=weyland
POD=mlflow-upgrade-drill
CM=mlflow-upgrade-drill-scripts
LIB="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)/lib/mlflow-upgrade-drill"

# drill_verdict <log> — the decision, on the drill's own output. Prints the verdict; returns 0 / 1 / 2.
drill_verdict() {
  local log="$1" bad="" before after from to secs n
  [ -s "$log" ] || { echo "NOT A PASS: the drill printed nothing"; return 2; }
  grep -q '^restore errors: 0$' "$log" || bad="${bad}; the restore reported errors"
  grep -qE '^upgrade: ok [0-9]+$' "$log" || bad="${bad}; the upgrade did not run cleanly"
  before="$(grep '^counts-before: ' "$log" | head -1 | sed 's/^counts-before: //')"
  after="$(grep '^counts-after: ' "$log" | head -1 | sed 's/^counts-after: //')"
  [ -n "$before" ] && [ -n "$after" ] || bad="${bad}; no row counts"
  if [[ "$before$after" == *MISSING* ]]; then bad="${bad}; a counted table is missing"
  elif [ "$before" != "$after" ]; then bad="${bad}; row counts changed (before: ${before}| after: ${after})"; fi
  grep -q '^health: OK$' "$log" || bad="${bad}; the upgraded server did not answer /health"
  n="$(sed -n 's/^endpoints: \([0-9][0-9]*\)$/\1/p' "$log" | head -1)"
  [ -n "$n" ] && [ "$n" -gt 0 ] || bad="${bad}; the upgraded server lists no gateway endpoints"
  grep -q '^chat: ok ' "$log" || bad="${bad}; the gateway did not answer a real chat request"
  ! grep -qE '^kek: (rotation FAILED|MLFLOW_CRYPTO_KEK_VERSION must)' "$log" || bad="${bad}; the KEK rotation failed"
  if [ -n "$bad" ]; then echo "DRILL FAILED${bad}"; return 1; fi
  from="$(sed -n 's/^alembic-before: //p' "$log" | head -1)"; to="$(sed -n 's/^alembic-after: //p' "$log" | head -1)"
  secs="$(sed -n 's/^upgrade: ok //p' "$log" | head -1)"
  echo "PASS: ${from} -> ${to} in ${secs} s; counts unchanged; server answers, ${n} gateway endpoint(s); a real gateway chat answered"
}

# manifest_env <manifest> — the live mlflow container's LITERAL env values as NAME=VALUE lines (secret-sourced entries
# are skipped, never copied). manifest_workers <manifest> — its `--workers N`. The drill runs production's config: on
# 2026-10-25 a drill with its own config (one worker, no gateway env) passed 3.17.2 while production's gateway failed.
manifest_env() {
  python3 -c '
import json, sys, yaml
for doc in yaml.safe_load_all(open(sys.argv[1])):
    if not doc or doc.get("kind") != "Deployment":
        continue
    for c in doc["spec"]["template"]["spec"]["containers"]:
        if c.get("name") == "mlflow":
            for e in c.get("env") or []:
                if "value" in e:
                    print(json.dumps({"name": e["name"], "value": str(e["value"])}))
                elif e["name"].startswith("MLFLOW_") and "valueFrom" in e:
                    # MLflow settings that come from a Secret (the KEK passphrase) as the SAME Secret reference: the
                    # drill must decrypt with the production key. DB credentials (POSTGRES_*) are never copied.
                    print(json.dumps({"name": e["name"], "valueFrom": e["valueFrom"]}))
            sys.exit(0)
sys.exit("no mlflow container in " + sys.argv[1])' "$1"
}
manifest_workers() {
  local w
  # the command only, never comments (the manifest's comments explain `--workers 1` vs 2)
  w="$({ grep -vE '^[[:space:]]*#' "$1" 2>/dev/null | grep -oE -- '--workers [0-9]+' || true; } | awk '{print $2}' | sort -u)"
  [ "$(printf '%s\n' "$w" | grep -c .)" -eq 1 ] || { echo "cannot tell the live --workers: not exactly one in $1"; return 2; }
  printf '%s\n' "$w"
}

# db_scheme <manifest> — the ONE SQLAlchemy URI scheme the live MLflow command uses (postgresql, postgresql+psycopg2…).
# The drill connects with the same scheme, so it fails exactly where production would: on 2026-10-24 a bare
# postgresql:// under 3.17.2's SQLAlchemy 2.1 picked the psycopg (v3) driver the image does not have.
db_scheme() {
  local found
  # `|| true`: no match must reach the count below (exit 2, named), not trip set -e/pipefail (exit 1)
  found="$({ grep -oE '"postgresql(\+[a-z0-9]+)?://' "$1" 2>/dev/null || true; } | tr -d '"' | sed 's#://$##' | sort -u)"
  [ "$(printf '%s\n' "$found" | grep -c .)" -eq 1 ] \
    || { echo "cannot tell the live URI scheme: not exactly one in $1 (found: ${found:-none})"; return 2; }
  printf '%s\n' "$found"
}

# judge <pod phase> <log> — a pod that RAN (Succeeded, or Failed with output) is judged on what it printed; anything
# else could not run.
judge() {
  case "$1" in
    Succeeded) drill_verdict "$2" ;;
    Failed) if [ -s "$2" ]; then drill_verdict "$2"; else echo "NOT A PASS: the drill pod failed and printed nothing"; return 2; fi ;;
    *) echo "NOT A PASS: the drill pod ended in phase '${1:-unknown}'"; return 2 ;;
  esac
}

[ -n "${MLFLOW_DRILL_LIB:-}" ] && return 0 2>/dev/null

IMAGE="${1:-}"
[ -n "$IMAGE" ] || { echo "usage: scripts/mlflow-upgrade-drill.sh <image>" >&2; exit 2; }
[[ "$IMAGE" =~ ^[a-z0-9][a-z0-9./_:@-]*$ ]] || { echo "not an image reference: $IMAGE" >&2; exit 2; }
for f in pg.sh mlflow.sh; do [ -r "$LIB/$f" ] || { echo "cannot read $LIB/$f" >&2; exit 2; }; done
MANIFEST="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)/nodes/mother/lab/weyland-platform/k8s/mlflow/mlflow.yaml"
SCHEME="$(db_scheme "$MANIFEST")" || { echo "$SCHEME" >&2; exit 2; }
WORKERS="$(manifest_workers "$MANIFEST")" || { echo "$WORKERS" >&2; exit 2; }
LIVE_ENV="$(manifest_env "$MANIFEST")" || { echo "cannot read the live container env from $MANIFEST" >&2; exit 2; }
echo "→ the live server: --workers ${WORKERS}; env $(printf '%s\n' "$LIVE_ENV" | python3 -c 'import json,sys; print(" ".join(json.loads(l)["name"] for l in sys.stdin if l.strip()))') (as in the manifest; Secret refs stay refs)"
echo "→ the live command connects as ${SCHEME}:// (from k8s/mlflow/mlflow.yaml); the drill uses the same"

cleanup() {
  kubectl -n "$NS" delete pod "$POD" --ignore-not-found --wait=false >/dev/null 2>&1 || true
  kubectl -n "$NS" delete configmap "$CM" --ignore-not-found >/dev/null 2>&1 || true
}
trap cleanup EXIT
cleanup
kubectl -n "$NS" wait --for=delete pod/"$POD" --timeout=120s >/dev/null 2>&1 || true
# The SAME KEK-rotation script production runs at server start, taken from its ConfigMap (B227 follow-on).
KEK_CM="$(dirname "$MANIFEST")/kek-rotate-configmap.yaml"
KEK_SH="$(mktemp)"
python3 -c 'import sys, yaml; open(sys.argv[2], "w").write(yaml.safe_load(open(sys.argv[1]))["data"]["rotate-kek-if-needed.sh"])' \
  "$KEK_CM" "$KEK_SH" || { echo "cannot read the rotation script from $KEK_CM" >&2; exit 2; }
kubectl -n "$NS" create configmap "$CM" --from-file=pg.sh="$LIB/pg.sh" --from-file=mlflow.sh="$LIB/mlflow.sh" \
  --from-file=rotate-kek-if-needed.sh="$KEK_SH" >/dev/null
rm -f "$KEK_SH"

python3 -c '
import json, sys
image, pod, cm, scheme, workers, live_env = sys.argv[1:]
env = [{"name": "MLFLOW_DRILL_DB_SCHEME", "value": scheme}, {"name": "MLFLOW_DRILL_WORKERS", "value": workers}]
env += [json.loads(l) for l in live_env.splitlines() if l]   # k8s env objects: literal values + MLFLOW_* Secret refs
mounts = [{"name": "s", "mountPath": "/drill", "readOnly": True}, {"name": "shared", "mountPath": "/shared"}]
print(json.dumps({"apiVersion": "v1", "kind": "Pod",
  "metadata": {"name": pod, "labels": {"app": pod, "sidecar.istio.io/inject": "false"}},
  "spec": {"nodeName": "mother", "restartPolicy": "Never", "automountServiceAccountToken": False,
    "containers": [
      {"name": "pg", "image": "postgres:17-alpine", "command": ["sh", "/drill/pg.sh"],
       "securityContext": {"runAsUser": 70, "runAsGroup": 70},
       "resources": {"requests": {"memory": "256Mi", "cpu": "250m"}, "limits": {"memory": "2Gi"}},
       "volumeMounts": mounts + [{"name": "b", "mountPath": "/backup", "readOnly": True}]},
      {"name": "mlflow", "image": image, "imagePullPolicy": "IfNotPresent", "command": ["sh", "/drill/mlflow.sh"],
       "env": env,
       "resources": {"requests": {"memory": "512Mi", "cpu": "250m"}, "limits": {"memory": "4Gi"}},
       "volumeMounts": mounts}],
    "securityContext": {"fsGroup": 70},
    "volumes": [{"name": "b", "hostPath": {"path": "/mnt/minio/backups", "type": "Directory"}},
                {"name": "s", "configMap": {"name": cm}},
                {"name": "shared", "emptyDir": {}}]}}))
' "$IMAGE" "$POD" "$CM" "$SCHEME" "$WORKERS" "$LIVE_ENV" | kubectl -n "$NS" apply -f - >/dev/null

echo "→ drilling $IMAGE on a restored copy of the mlflow database (the restore streams ~2 GB; ~10 min)…"
phase=""
for _ in $(seq 1 160); do
  phase="$(kubectl -n "$NS" get pod "$POD" -o jsonpath='{.status.phase}' 2>/dev/null || true)"
  case "$phase" in Succeeded|Failed) break;; esac
  sleep 15
done
LOG="$(mktemp)"
{ kubectl -n "$NS" logs "$POD" -c pg 2>/dev/null | grep -v -i 'locale\|initdb' || true
  kubectl -n "$NS" logs "$POD" -c mlflow 2>/dev/null || true; } > "$LOG"
cat "$LOG"
rc=0; judge "$phase" "$LOG" || rc=$?
rm -f "$LOG"
exit "$rc"
