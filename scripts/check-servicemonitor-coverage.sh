#!/usr/bin/env bash
# ServiceMonitor / workload / scrape reconciliation (B148).
#
# WHY THIS EXISTS: `data-mesh/trino`'s ServiceMonitor was created, committed, Argo-applied and
# `kubectl get`-able for 59 days while exporting exactly zero metrics. Nothing in the estate could
# say so, because the condition has NO POSITIVE SIGNAL anywhere:
#
#   kubectl get servicemonitor trino  -> exists, 60d          ✅
#   up{job="trino"}                   -> no data              (reads as "no traffic", not "broken")
#   the Grafana panel                 -> empty                (indistinguishable from idle)
#
# Prometheus only creates a scrape pool once discovery matches at least one endpoint, so a
# ServiceMonitor whose selector matches NOTHING is invisible in /api/v1/targets. It is only found by
# enumerating what SHOULD exist and subtracting what DOES.
#
# IT IS NOT A BINARY "IS IT SCRAPING" CHECK. It reconciles three planes, and any disagreement is a
# defect:
#
#   INTENDED  .spec.replicas on the live workload
#   ACTUAL    .status.readyReplicas
#   OBSERVED  the Prometheus scrape-pool target count
#
# Reading INTENDED from the cluster is legitimate ONLY because Argo selfHeal (on 75 of 78 apps; the 3
# without are ConfigMap-only) continuously overwrites .spec.replicas from git — which makes the field
# a cached read of git rather than self-graded cluster state. Store sleep deliberately has no external
# scaler for the same reason (k8s/argocd/applications/helm-apps.yaml:267-275): ceding /spec/replicas
# would leave the sleep state living only in the cluster.
#
# Without the INTENDED plane, `0 replicas` is ambiguous input rather than an answer: deliberately
# parked and crashed-at-3am are byte-identical.
#
#   usage: scripts/check-servicemonitor-coverage.sh [--list]
#          --list   print every ServiceMonitor and its verdict, exit 0
#
# INPUTS. By default it reads live ServiceMonitors + workloads with kubectl and the scrape pools from
# Prometheus via the API proxy. For testing point these at fixtures instead:
#
#   SM_SNAPSHOT_JSON  [{"ns":…,"name":…,"intended":N,"actual":N}]  — skips kubectl
#   TARGETS_JSON      a /api/v1/targets response body              — skips Prometheus
#
# EXIT CODES are distinct on purpose. 1 = the estate has a defect. 2 = the guard could not do its job.
# Conflating them means a broken guard reads exactly like a broken cluster.
set -euo pipefail

. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

PROM_POD="${PROM_POD:-prometheus-monitoring-kube-prometheus-prometheus-0}"
PROM_NS="${PROM_NS:-monitoring}"

# --- accepted, with the reason -------------------------------------------------------------------
#
# One row per tolerated ServiceMonitor: <ns/name>|<why it legitimately matches nothing>
#
# Same posture as check-pip-audit-ignores.sh: an exception must state the CONDITION that makes it
# fine, so a reader can re-check it rather than trust it. Keep this SHORT — every entry is a
# ServiceMonitor this guard has stopped looking at.
ACCEPTED=(
  "monitoring/monitoring-kube-prometheus-kube-etcd|kube-prometheus-stack ships this by default for a kubeadm control plane. k3s embeds its datastore in the server process and runs no etcd Service, so the selector can never match anything on this cluster. Chart-owned, so it cannot be deleted without a values override that would drift on the next chart bump."
)

is_accepted() { # is_accepted <ns/name>
  local row e_entry
  for row in "${ACCEPTED[@]}"; do
    IFS="|" read -r e_entry _ <<<"$row"
    [ "$e_entry" = "$1" ] && return 0
  done
  return 1
}

accepted_reason() { # accepted_reason <ns/name>
  local row e_entry e_reason
  for row in "${ACCEPTED[@]}"; do
    IFS="|" read -r e_entry e_reason <<<"$row"
    [ "$e_entry" = "$1" ] && { printf '%s' "$e_reason"; return 0; }
  done
  return 1
}

# --- the decision --------------------------------------------------------------------------------
#
# classify <intended> <actual> <targets> -> prints ONE verdict token, exit 0.
#                                           Non-numeric input -> exit non-zero, print nothing.
#
# TODO(you): implement. The matrix, and why each cell is what it is:
#
#   INTENDED  ACTUAL  OBSERVED  verdict    meaning
#   >0        >0      >0        ok         running and scraped
#   >0        >0      0         blind      RUNNING AND UNMONITORED  <- trino, the B148 defect
#   >0        0       *         down       should be up and is not
#   0         0       0         sleeping   deliberately parked, committed as replicas: 0
#   0         >0      *         zombie     awake without a declaration
#   0         0       >0        stale      scraped after being parked; targets should have drained
#
# Two things to be careful about, both of which the tests will catch:
#
#   - A rolling update briefly has actual < intended (3/2/2). That is `ok`, not `down` — something is
#     ready and something is scraped. Ordering the branches wrong pages you on every deploy.
#   - Non-numeric input must FAIL rather than default to 0. An unparsed field arriving as "" or
#     "<none>" that silently becomes 0 classifies a broken lookup as `sleeping` — a clean pass over a
#     workload nobody measured, which is the exact bug this guard exists to catch.
classify() { # classify <intended> <actual> <targets>
  local intended="${1-}" actual="${2-}" targets="${3-}" n
  # Accept a non-negative integer, or the single sentinel -1. Say nothing on stdout when refusing.
  # A sentinel is a contract, not a licence: -2 means a lookup went wrong in a way nobody designed
  # for, and that has to be loud rather than swept into the -1 branch.
  for n in "$intended" "$actual" "$targets"; do
    case "$n" in
      -1)          continue ;;
      ''|*[!0-9]*) return 1 ;;
    esac
  done
  # `targets` is a real count from Prometheus and never a sentinel.
  [ "$targets" -lt 0 ] && return 1

  # NOTHING IN KUBERNETES DECLARES INTENT for this monitor (-1). Found live on
  # monitoring-kube-prometheus-apiserver (selector-less Service, manual Endpoints) and -kubelet (a
  # host process per node). Neither has a workload and neither ever will.
  #
  # The INTENDED plane is simply unavailable here, so the verdict rests on the OBSERVED plane alone:
  # an active healthy scrape is direct evidence the monitor works, and no scrape at all leaves no
  # evidence from any plane. Deliberately NOT an ACCEPTED entry — that would stop checking them, and
  # a kubelet scrape dying is exactly what this guard is for.
  if [ "$intended" -eq -1 ] || [ "$actual" -eq -1 ]; then
    [ "$targets" -gt 0 ] && { echo unmanaged; return 0; }
    echo orphan; return 0
  fi

  if [ "$intended" -gt 0 ]; then
    # Declared up. Nothing ready at all is an outage; the monitoring verdict cannot be trusted.
    [ "$actual" -eq 0 ] && { echo down; return 0; }
    # SOMETHING is ready. Deliberately not comparing actual against intended: a rolling update sits
    # at 3/2 for a minute and that is not a monitoring defect. The only question left is whether
    # what IS running is being scraped.
    [ "$targets" -gt 0 ] && { echo ok; return 0; }
    echo blind; return 0
  fi

  # Declared parked (replicas: 0 committed to git, enforced by selfHeal).
  [ "$actual" -gt 0 ] && { echo zombie; return 0; }
  [ "$targets" -gt 0 ] && { echo stale; return 0; }
  echo sleeping
}

# is_failing <verdict> -> 0 when the verdict should fail the run.
#
# FAILS CLOSED on an unknown token: a verdict this function has never heard of is a bug in the guard,
# and a bug in the guard must not read as a pass.
is_failing() { # is_failing <verdict>
  case "${1-}" in
    ok|sleeping|unmanaged) return 1 ;;
    *)                     return 0 ;;
  esac
}

# --- scrape pools --------------------------------------------------------------------------------
#
# pool_targets <targets-json> <ns> <name> -> the count of HEALTHY targets in that ServiceMonitor's
# scrape pools. Prometheus names a pool `serviceMonitor/<ns>/<name>/<endpointIndex>`, so a monitor
# with three endpoints owns /0 /1 /2 and all three count.
#
# EXACT match on the ns/name segments, never a prefix: `trino` must not be satisfied by
# `trino-worker`. Substring matching here would invent coverage that does not exist.
#
# Counts only HEALTHY targets. A target that is discovered but fails every scrape yields no series;
# counting it would report coverage that is not there.
#
# UNREADABLE OR MALFORMED INPUT IS FATAL, never 0. "0 targets" is a finding; "I could not read the
# file" is a broken guard, and one `|| echo 0` between them turns every ServiceMonitor into a pass.
pool_targets() { # pool_targets <targets-json> <ns> <name>
  local f="${1:?usage: pool_targets <targets-json> <ns> <name>}" ns="${2:?}" name="${3:?}"
  [ -r "$f" ] || { echo "FATAL: cannot read the targets JSON: $f" >&2; return 1; }
  python3 - "$f" "$ns" "$name" <<'PY' || return 1
import json, sys
path, ns, name = sys.argv[1], sys.argv[2], sys.argv[3]
try:
    with open(path, encoding="utf-8") as fh:
        doc = json.load(fh)
except Exception as exc:
    print(f"FATAL: could not parse {path}: {exc}", file=sys.stderr)
    raise SystemExit(1)
targets = (doc.get("data") or {}).get("activeTargets")
if targets is None:
    print(f"FATAL: {path} has no data.activeTargets", file=sys.stderr)
    raise SystemExit(1)
want = ("serviceMonitor", ns, name)
n = 0
for t in targets:
    parts = (t.get("scrapePool") or "").split("/")
    # kind / ns / name / endpointIndex — exact on the first three, so `trino` never matches
    # `trino-worker`.
    if len(parts) == 4 and tuple(parts[:3]) == want and t.get("health") == "up":
        n += 1
print(n)
PY
}

# --- reading the live estate -----------------------------------------------------------------------
#
# servicemonitor_rows -> one JSON array of {ns, name, intended, actual}.
#
# `intended` is .spec.replicas of the workload behind the ServiceMonitor's Service, and `actual` is
# .status.readyReplicas. A ServiceMonitor with no resolvable workload gets intended=-1, which is not
# a number the matrix accepts — it must be documented in ACCEPTED or the run fails.
servicemonitor_rows() {
  if [ -n "${SM_SNAPSHOT_JSON:-}" ]; then
    [ -r "$SM_SNAPSHOT_JSON" ] || { echo "FATAL: cannot read $SM_SNAPSHOT_JSON" >&2; return 1; }
    cat "$SM_SNAPSHOT_JSON"
    return 0
  fi
  # VIA TEMP FILES, NOT argv. The first cut passed all three blobs as arguments and died with
  # "Argument list too long" — 32 ServiceMonitors + ~90 Services + ~140 workloads is well past
  # MAX_ARG_STRLEN. It failed loudly with exit 2 rather than silently producing an empty list, which
  # is the only reason that was a five-minute fix instead of another guard that measures nothing.
  local dir; dir="$(mktemp -d)"
  trap 'rm -rf "$dir"' RETURN
  kubectl get servicemonitors -A -o json >"$dir/sm.json" 2>/dev/null || {
    echo "FATAL: could not list ServiceMonitors" >&2; return 1; }
  kubectl get svc -A -o json >"$dir/svc.json" 2>/dev/null || {
    echo "FATAL: could not list Services" >&2; return 1; }
  kubectl get deploy,statefulset,daemonset -A -o json >"$dir/wl.json" 2>/dev/null || {
    echo "FATAL: could not list workloads" >&2; return 1; }
  python3 - "$dir/sm.json" "$dir/svc.json" "$dir/wl.json" <<'PY'
import json, sys
sms  = json.load(open(sys.argv[1], encoding="utf-8"))["items"]
svcs = json.load(open(sys.argv[2], encoding="utf-8"))["items"]
wls  = json.load(open(sys.argv[3], encoding="utf-8"))["items"]

def matches(selector, labels):
    return selector and all(labels.get(k) == v for k, v in selector.items())

rows = []
for sm in sms:
    ns   = sm["metadata"]["namespace"]
    name = sm["metadata"]["name"]
    sel  = (sm["spec"].get("selector") or {}).get("matchLabels") or {}
    # namespaceSelector.matchNames widens the search; absent means the monitor's own namespace.
    nsel = sm["spec"].get("namespaceSelector") or {}
    scopes = nsel.get("matchNames") or ([] if nsel.get("any") else [ns])
    intended, actual = -1, -1
    for svc in svcs:
        sns = svc["metadata"]["namespace"]
        if scopes and sns not in scopes:
            continue
        if not matches(sel, svc["metadata"].get("labels") or {}):
            continue
        psel = svc["spec"].get("selector") or {}
        for w in wls:
            if w["metadata"]["namespace"] != sns:
                continue
            wlab = ((w["spec"].get("template") or {}).get("metadata") or {}).get("labels") or {}
            if psel and all(wlab.get(k) == v for k, v in psel.items()):
                st = w.get("status") or {}
                if w["kind"] == "DaemonSet":
                    intended = st.get("desiredNumberScheduled", 0)
                    actual   = st.get("numberReady", 0)
                else:
                    intended = w["spec"].get("replicas", 1)
                    actual   = st.get("readyReplicas", 0)
                break
        if intended != -1:
            break
    rows.append({"ns": ns, "name": name, "intended": intended, "actual": actual})
print(json.dumps(rows))
PY
}

targets_json() {
  if [ -n "${TARGETS_JSON:-}" ]; then
    printf '%s' "$TARGETS_JSON"
    return 0
  fi
  local tmp; tmp="$(mktemp)"
  kubectl get --raw \
    "/api/v1/namespaces/$PROM_NS/pods/$PROM_POD:9090/proxy/api/v1/targets?state=any" >"$tmp" 2>/dev/null || {
      echo "FATAL: could not reach Prometheus at $PROM_NS/$PROM_POD" >&2; rm -f "$tmp"; return 1; }
  printf '%s' "$tmp"
}

main() {
  local list_only=0
  [ "${1-}" = "--list" ] && list_only=1
  command -v python3 >/dev/null 2>&1 || { echo "❌ python3 not found on PATH" >&2; exit 2; }

  local rows tfile
  rows="$(servicemonitor_rows)"   || exit 2
  tfile="$(targets_json)"         || exit 2

  local total=0 failed=0
  local line ns name intended actual targets verdict
  while IFS=$'\t' read -r ns name intended actual; do
    [ -n "${ns:-}" ] || continue
    total=$((total + 1))
    local entry="$ns/$name"

    if is_accepted "$entry"; then
      [ "$list_only" -eq 1 ] && printf '  ACCEPTED %-52s (documented exception)\n' "$entry"
      continue
    fi

    if ! targets="$(pool_targets "$tfile" "$ns" "$name")"; then
      echo "  ❌ $entry — could not read scrape pools" >&2
      exit 2
    fi

    if ! verdict="$(classify "$intended" "$actual" "$targets")"; then
      echo "  ❌ $entry — unclassifiable (intended=$intended actual=$actual targets=$targets)" >&2
      echo "     A ServiceMonitor with no resolvable workload must be documented in ACCEPTED." >&2
      failed=$((failed + 1)); continue
    fi

    if is_failing "$verdict"; then
      printf '  ❌ %-52s %-9s intended=%s actual=%s targets=%s\n' \
        "$entry" "$verdict" "$intended" "$actual" "$targets" >&2
      failed=$((failed + 1))
    elif [ "$list_only" -eq 1 ] || [ "$verdict" = "sleeping" ]; then
      printf '  %s %-52s %-9s intended=%s actual=%s targets=%s\n' \
        "$([ "$verdict" = sleeping ] && echo '💤' || echo 'ok')" \
        "$entry" "$verdict" "$intended" "$actual" "$targets"
    fi
  done < <(printf '%s' "$rows" | python3 -c "
import json, sys
for r in json.load(sys.stdin):
    print('\t'.join(str(r[k]) for k in ('ns','name','intended','actual')))
")

  [ -z "${TARGETS_JSON:-}" ] && rm -f "$tfile"

  if [ "$total" -eq 0 ]; then
    echo "❌ ZERO ServiceMonitors found. 'Checked nothing, found nothing' is the exact shape of bug" >&2
    echo "   this guard exists to catch; it must never be a clean pass." >&2
    exit 2
  fi

  [ "$list_only" -eq 1 ] && { echo "listed $total ServiceMonitor(s)."; return 0; }

  if [ "$failed" -ne 0 ]; then
    echo >&2
    echo "❌ $failed of $total ServiceMonitor(s) disagree with the workload they monitor." >&2
    echo "   A monitor that exists but scrapes nothing is how data-mesh/trino exported zero metrics" >&2
    echo "   for 59 days while every affirmative check came back clean (B148)." >&2
    exit 1
  fi
  echo "OK — $total ServiceMonitor(s), every one reconciled against its workload."
}

if [ -z "${SERVICEMONITOR_COVERAGE_LIB:-}" ]; then
  main "$@"
fi
