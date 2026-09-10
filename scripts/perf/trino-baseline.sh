#!/usr/bin/env bash
# B104 — Trino perf baseline (in-cluster). Trino is ClusterIP-only (trino.data-mesh.svc:8080), so k6 runs
# as an ephemeral Job IN data-mesh. Trino has NO Istio sidecar, so the Job sets sidecar.istio.io/inject
# =false and reaches trino:8080 over plain HTTP. LIGHT `SELECT 1` at low VUs — Trino's 4-6Gi heap has an
# OOM history; NEVER point this at heavy aggregations. On-demand; records to tests/perf/baseline.tsv; cleans up.
#   env: PERF_VUS (default 3) · PERF_DURATION (default 20s) · TRINO_NS (default data-mesh) · K6_IMAGE
set -uo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
BASELINE="${PERF_BASELINE_FILE:-$REPO_ROOT/tests/perf/baseline.tsv}"
NS="${TRINO_NS:-data-mesh}"
VUS="${PERF_VUS:-3}"
DUR="${PERF_DURATION:-20s}"
K6_IMG="${K6_IMAGE:-grafana/k6:latest}"
export KUBECONFIG="${KUBECONFIG:-$HOME/.kube/config}"

die() { printf '%s\n' "$*" >&2; exit 2; }
command -v kubectl >/dev/null 2>&1 || die "kubectl not found"
kubectl -n "$NS" get svc trino >/dev/null 2>&1 || die "trino svc not found in ns $NS"
[ -f "$REPO_ROOT/scripts/perf/trino.js" ] || die "missing scripts/perf/trino.js"

cleanup() {
  kubectl -n "$NS" delete configmap perf-trino-k6 --ignore-not-found >/dev/null 2>&1
  kubectl -n "$NS" delete job perf-trino-k6 --ignore-not-found >/dev/null 2>&1
}
trap cleanup EXIT
cleanup   # clear any prior run

kubectl -n "$NS" create configmap perf-trino-k6 \
  --from-file=trino.js="$REPO_ROOT/scripts/perf/trino.js" --dry-run=client -o yaml \
  | kubectl -n "$NS" apply -f - >/dev/null || die "could not create the k6 configmap"

cat <<EOF | kubectl -n "$NS" apply -f - >/dev/null || die "could not apply the k6 Job"
apiVersion: batch/v1
kind: Job
metadata:
  name: perf-trino-k6
spec:
  backoffLimit: 0
  ttlSecondsAfterFinished: 300
  template:
    metadata:
      annotations:
        sidecar.istio.io/inject: "false"
    spec:
      restartPolicy: Never
      containers:
        - name: k6
          image: $K6_IMG
          command: ["k6", "run", "--quiet", "/scripts/trino.js"]
          env:
            - {name: BASE, value: "http://trino:8080"}
            - {name: SQL, value: "SELECT 1"}
            - {name: VUS, value: "$VUS"}
            - {name: DURATION, value: "$DUR"}
          volumeMounts:
            - {name: s, mountPath: /scripts}
      volumes:
        - {name: s, configMap: {name: perf-trino-k6}}
EOF

printf '→ trino  (SELECT 1  vus=%s  dur=%s  in-cluster Job, sidecar off)\n' "$VUS" "$DUR"
kubectl -n "$NS" wait --for=condition=complete job/perf-trino-k6 --timeout=180s >/dev/null 2>&1 || true
line="$(kubectl -n "$NS" logs job/perf-trino-k6 2>/dev/null | grep '^PERFLINE')" || true
[ -n "$line" ] || die "no PERFLINE from the Trino k6 Job — inspect: kubectl -n $NS logs job/perf-trino-k6"

# shellcheck disable=SC2086
set -- $line   # PERFLINE qps p50 p95 p99 err httphops
printf '  qps=%s  p50=%sms  p95=%sms  p99=%sms  err=%s%%  http_hops=%s\n' "$2" "$3" "$4" "$5" "$6" "$7"
mkdir -p "$(dirname "$BASELINE")"
[ -f "$BASELINE" ] || printf 'target\trps\tp50_ms\tp95_ms\tp99_ms\terr_pct\treqs\tvus\tdur\ttimestamp\n' > "$BASELINE"
printf 'trino\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
  "$2" "$3" "$4" "$5" "$6" "$7" "$VUS" "$DUR" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$BASELINE"
printf 'baseline → %s\n' "$BASELINE"
