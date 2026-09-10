#!/usr/bin/env bash
# B104 — HTTP perf baseline runner. ON-DEMAND, bounded, record-mode. Runs k6 (grafana/k6 image) against
# each service's LIGHT serving-plane endpoints and records rps / p50 / p95 / p99 / err% to
# tests/perf/baseline.tsv, so later runs have a baseline to compare against. NEVER scheduled.
#
# WHY LIGHT ENDPOINTS: this measures each service's own request-serving (throughput + latency + concurrency
# handling), NOT upstream LLM inference (cost/GPU/slow) or heavy Trino aggregations (4-6Gi heap, OOM history).
#   toolserver  http://192.168.1.243:30080   /health,/ready
#   gateway     http://192.168.1.243:30400   /health/readiness   (LiteLLM serving-plane; no completion)
# Trino is in-cluster only (trino.data-mesh.svc:8080) — see scripts/perf/trino-baseline-job.yaml.
#
# BOUNDED BY DESIGN: mother is swapless with ~4.6Gi headroom (B134/B99), so a load test is itself a risk.
# Low VUs + light endpoints keep it negligible; raise PERF_VUS only after confirming the node is comfortable.
#   usage: scripts/perf-baseline.sh [toolserver|gateway|all]   (default: all LAN targets)
#   env:   PERF_VUS (default 10) · PERF_DURATION (default 30s) · PERF_BASELINE_FILE · K6_IMAGE
#
# GRAFANA (optional): set K6_PROMETHEUS_RW_SERVER_URL to a Prometheus remote-write endpoint and each run
# also streams live metrics there (tagged target=<name>) for the "k6 Perf" dashboard
# (k8s/monitoring/k6-perf-dashboard.yaml). The receiver is already enabled on kube-prometheus-stack, but
# it is a ClusterIP — reachable from an in-cluster k6 (see scripts/perf/trino-baseline.sh) but NOT from
# this LAN docker run unless you expose it (NodePort/ingress) or point at a LAN-reachable RW URL. The TSV
# baseline is written either way; RW only adds the live dashboard feed.
set -uo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
BASELINE="${PERF_BASELINE_FILE:-$REPO_ROOT/tests/perf/baseline.tsv}"
K6_IMG="${K6_IMAGE:-grafana/k6:latest}"
VUS="${PERF_VUS:-10}"
DUR="${PERF_DURATION:-30s}"
SCRIPT="$REPO_ROOT/scripts/perf/baseline.js"
K6_RW_URL="${K6_PROMETHEUS_RW_SERVER_URL:-}"
RW_TREND="${K6_PROMETHEUS_RW_TREND_STATS:-p(95),p(99),avg}"

die() { printf '%s\n' "$*" >&2; exit 2; }
command -v docker >/dev/null 2>&1 || die "docker not found (k6 runs via the $K6_IMG image)"
[ -f "$SCRIPT" ] || die "missing k6 script: $SCRIPT"
mkdir -p "$(dirname "$BASELINE")"
[ -f "$BASELINE" ] || printf 'target\trps\tp50_ms\tp95_ms\tp99_ms\terr_pct\treqs\tvus\tdur\ttimestamp\n' > "$BASELINE"

run() { # run <name> <base> <paths> [auth]
  local name="$1" base="$2" paths="$3" auth="${4:-}" out
  printf '→ %s  (%s  paths=%s  vus=%s  dur=%s%s)\n' "$name" "$base" "$paths" "$VUS" "$DUR" \
    "$([ -n "$K6_RW_URL" ] && echo '  +remote-write' || true)"
  # Optional Prometheus remote-write: extra k6 flags + env, only when K6_RW_URL is set. Guarded array
  # expansion (${a[@]+"${a[@]}"}) because an empty array under `set -u` is an unbound-variable error on
  # bash < 4.4. --tag target=<name> labels the series so the dashboard can legend by target.
  local k6flags=(run --quiet) rwenv=()
  if [ -n "$K6_RW_URL" ]; then
    k6flags=(run -o experimental-prometheus-rw --quiet --tag "target=$name")
    rwenv=(-e "K6_PROMETHEUS_RW_SERVER_URL=$K6_RW_URL" -e "K6_PROMETHEUS_RW_TREND_STATS=$RW_TREND")
  fi
  # --network host so the container reaches the LAN NodePorts. handleSummary prints PERFLINE to stdout.
  out="$(docker run --rm --network host -v "$SCRIPT:/b.js:ro" \
        -e BASE="$base" -e PATHS="$paths" -e VUS="$VUS" -e DURATION="$DUR" -e AUTH="$auth" \
        ${rwenv[@]+"${rwenv[@]}"} \
        "$K6_IMG" "${k6flags[@]}" /b.js 2>/dev/null | grep '^PERFLINE')" || true
  [ -n "$out" ] || { printf '  x no result (k6 failed or target unreachable)\n' >&2; return 1; }
  # PERFLINE rps p50 p95 p99 err reqs
  # shellcheck disable=SC2086
  set -- $out
  printf '  rps=%s  p50=%sms  p95=%sms  p99=%sms  err=%s%%  reqs=%s\n' "$2" "$3" "$4" "$5" "$6" "$7"
  printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\t%s\n' \
    "$name" "$2" "$3" "$4" "$5" "$6" "$7" "$VUS" "$DUR" "$(date -u +%Y-%m-%dT%H:%M:%SZ)" >> "$BASELINE"
}

target="${1:-all}"
rc=0
case "$target" in
  toolserver|all) run toolserver "http://192.168.1.243:30080" "/health,/ready" || rc=1 ;;
esac
case "$target" in
  gateway|all)    run gateway    "http://192.168.1.243:30400" "/health/readiness" || rc=1 ;;
esac

printf '\nbaseline → %s\n' "$BASELINE"
exit "$rc"
