#!/usr/bin/env bash
# Alert coverage — every metric-emitting job is protected by a DOWN/absent alert, or a documented reason.
#
# THIRD of the observability-coverage guards, completing the set:
#   check-servicemonitor-coverage.sh (B148)  — is the service SCRAPED?        (Prometheus)
#   check-dashboard-coverage.sh               — is what's scraped VISUALIZED?  (Grafana)
#   check-alert-coverage.sh (this)            — is a down/absence ALERTED?     (PrometheusRules)
#
# COVERAGE MODEL. A job is covered when a down/absent alert protects it, by EITHER of:
#
#   (1) a JOB-SCOPED alert — an alerting rule whose expr is up/absent-flavoured (`up{…} == 0`,
#       `absent(up{…})`) AND names the job (`job="J"` / `job=~"pat"`). e.g. LancedbExporterDown,
#       KubeletDown. The dedicated, per-service alert.
#
#   (2) the BLANKET net — a down/absent alerting rule with NO job filter, so it fires for ANY scraped
#       job going down. kube-prometheus-stack ships this as `TargetDown`
#       (`count(up == 0) BY (…job…) / count(up) BY (…) > 10`). Because it groups BY job, one net rule
#       protects every job at once.
#
# WHY THIS SHAPE and not "a dedicated Down alert per service": that would flag ~32 of 38 jobs and demand
# ~30 alerts redundant with TargetDown — over-engineering for a lab. The REAL drift risk is the opposite:
# the blanket net gets removed (a kube-prometheus-stack values change disabling default rules, a bad
# PrometheusRule edit) and EVERY service silently loses down-alerting at once, with no positive signal —
# the same absence-as-success class as its two sibling guards. So this guard passes while the net (or a
# per-service alert) covers every job, and fails LOUD the moment a job is left unprotected.
#
#   usage: scripts/check-alert-coverage.sh [--list]
#          --list   print every job and its verdict (blanket / scoped / accepted / GAP), exit 0
#
# INPUTS (override for tests):
#   UP_RAW_FILE     a raw /api/v1/query body for `count by (job) (up)`   — skips the up query
#   RULES_JSON_FILE a `kubectl get prometheusrules -A -o json` body      — skips kubectl
#
# EXIT: 0 every job protected, 1 a job with no down alert (net gone / new-service gap), 2 guard broken.
set -euo pipefail

PROM_POD="${PROM_POD:-prometheus-monitoring-kube-prometheus-prometheus-0}"
PROM_NS="${PROM_NS:-monitoring}"

# --- accepted, with the reason -------------------------------------------------------------------
# One row per tolerated job: <job>|<why it needs no down alert>. State the CONDITION. Empty by design —
# the blanket TargetDown covers everything, so a gap here is a real finding, not a job to wave through.
ACCEPTED=()

is_accepted() { # is_accepted <job>
  local row e_entry
  for row in ${ACCEPTED[@]+"${ACCEPTED[@]}"}; do
    IFS="|" read -r e_entry _ <<<"$row"
    [ "$e_entry" = "$1" ] && return 0
  done
  return 1
}

# --- coverage --------------------------------------------------------------------------------------
#
# covered_jobs <up-file> <rules-json-file> -> the subset of up-jobs a down/absent alert protects.
#
# A blanket rule (up/absent with no job= selector) covers ALL up-jobs; a job-scoped down alert covers the
# jobs it names. Recording rules (no `alert:` key) are ignored — only alerting rules protect anything.
covered_jobs() {
  python3 - "$1" "$2" <<'PY'
import json, re, sys
up = [l.strip() for l in open(sys.argv[1]) if l.strip()]
try:
    doc = json.loads(open(sys.argv[2]).read())
except Exception as e:
    sys.stderr.write(f"FATAL: PrometheusRules JSON did not parse: {e}\n"); sys.exit(3)

scoped, patterns, blanket = set(), [], False
for pr in doc.get("items", []):
    for grp in (pr.get("spec", {}) or {}).get("groups") or []:
        for rule in grp.get("rules") or []:
            if "alert" not in rule:        # recording rule — protects nothing
                continue
            expr = rule.get("expr", "") or ""
            is_down = bool(re.search(r'\bup\b', expr) and (re.search(r'==\s*0', expr) or "absent(" in expr))
            if not is_down:
                continue
            lits = re.findall(r'job="([^"]+)"', expr)
            pats = re.findall(r'job=~"([^"]+)"', expr)
            if not lits and not pats:
                blanket = True             # a down/absent rule with no job filter fires for every job
            else:
                scoped.update(lits)
                patterns.extend(pats)

compiled = []
for p in patterns:
    try:
        compiled.append(re.compile(p))
    except re.error:
        pass
for j in up:
    if blanket or j in scoped or any(rx.fullmatch(j) for rx in compiled):
        print(j)
PY
}

# --- inputs ----------------------------------------------------------------------------------------

prom_query() { # prom_query <promql> -> raw /api/v1/query response body
  local q
  q="$(python3 -c "import urllib.parse,sys; print(urllib.parse.quote(sys.argv[1]))" "$1")" || return 1
  kubectl get --raw \
    "/api/v1/namespaces/$PROM_NS/pods/$PROM_POD:9090/proxy/api/v1/query?query=$q" 2>/dev/null
}

up_jobs() {
  local raw
  if [ -n "${UP_RAW_FILE:-}" ]; then raw="$(cat "$UP_RAW_FILE")"
  else raw="$(prom_query 'count by (job) (up)')" \
    || { echo "FATAL: could not reach Prometheus at $PROM_NS/$PROM_POD" >&2; return 1; }; fi
  printf '%s' "$raw" | python3 -c "
import json, sys
for s in json.load(sys.stdin).get('data', {}).get('result', []):
    j = s.get('metric', {}).get('job')
    if j: print(j)
" || { echo "FATAL: 'up' query result did not parse" >&2; return 1; }
}

rules_json() {
  if [ -n "${RULES_JSON_FILE:-}" ]; then cat "$RULES_JSON_FILE"; return 0; fi
  kubectl get prometheusrules -A -o json 2>/dev/null \
    || { echo "FATAL: could not list PrometheusRules" >&2; return 1; }
}

main() {
  local list_only=0
  [ "${1-}" = "--list" ] && list_only=1
  command -v python3 >/dev/null 2>&1 || { echo "❌ python3 not found on PATH" >&2; exit 2; }

  local ups rules upfile rulesfile coveredfile covered
  ups="$(up_jobs)"     || exit 2
  rules="$(rules_json)" || exit 2

  upfile="$(mktemp)"; rulesfile="$(mktemp)"; coveredfile="$(mktemp)"
  # shellcheck disable=SC2064
  trap "rm -f '$upfile' '$rulesfile' '$coveredfile'" RETURN
  printf '%s\n' "$ups" | awk 'NF' | sort -u > "$upfile"
  printf '%s'   "$rules" > "$rulesfile"

  local total; total="$(wc -l <"$upfile")"
  if [ "$total" -eq 0 ]; then
    echo "❌ ZERO scrape jobs found. 'Checked nothing, found nothing' is the exact shape of bug this" >&2
    echo "   guard exists to catch; it must never be a clean pass." >&2
    exit 2
  fi

  covered="$(covered_jobs "$upfile" "$rulesfile")" \
    || { echo "❌ coverage computation failed (PrometheusRules unreadable)" >&2; exit 2; }
  printf '%s\n' "$covered" | awk 'NF' | sort -u > "$coveredfile"

  local job gaps=0
  while IFS= read -r job; do
    [ -n "$job" ] || continue
    if grep -qxF "$job" "$coveredfile"; then
      [ "$list_only" -eq 1 ] && printf '  ok       %s\n' "$job"
    elif is_accepted "$job"; then
      [ "$list_only" -eq 1 ] && printf '  ACCEPTED %s (documented exception)\n' "$job"
    else
      printf '  ❌ GAP   %s — scraped, but no down/absent alert protects it (and the blanket net does not cover it)\n' "$job" >&2
      gaps=$((gaps + 1))
    fi
  done <"$upfile"

  if [ "$list_only" -eq 1 ]; then
    echo "listed $total scrape job(s)."
    return 0
  fi

  if [ "$gaps" -ne 0 ]; then
    echo >&2
    echo "❌ $gaps of $total scrape job(s) have no down-alert coverage." >&2
    echo "   Usually this means the BLANKET net (TargetDown) was removed or scoped away — every job with" >&2
    echo "   no dedicated up==0/absent(up) alert is now unprotected. Restore the net, add a per-service" >&2
    echo "   down alert, or (if covered elsewhere) document it in ACCEPTED with the reason." >&2
    exit 1
  fi
  echo "OK — $total scrape job(s), every one protected by a down/absent alert."
}

if [ -z "${ALERT_COVERAGE_LIB:-}" ]; then
  main "$@"
fi
