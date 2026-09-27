#!/usr/bin/env bash
# Dagster watchdog budget drift guard (B196). The Dagster sibling of check-cron-freshness-budgets.sh (which covers
# k8s CronJobs only). Asserts that the two surfaces carrying a Dagster schedule's cadence agree:
#
#   1. the ScheduleDefinitions in weyland_pipeline — cron + default_status (the TRUTH the daemon runs)
#   2. the BUDGETS block in k8s/dagster/freshness.yaml — the per-job staleness budget the watchdog alerts on
#
# WHY THIS EXISTS (found shipping B194, 2026-09-27):
#   - weyland_catalog_job / weyland_timeseries_job / datahub_catalog_emit_job went nightly on 2026-08-07 and kept
#     their 6-8h budgets: DagsterJobStale false-fired every 30 minutes for seven weeks. A permanently-lit alert is
#     worse than none — it trains the reader to ignore the channel.
#   - feast_materialize_job (daily) and registrations_reconcile_job (weekly) were RUNNING with no budget, so a stop
#     was invisible.
#
# RULES — each fails by name (exit 1):
#   - a RUNNING schedule whose job has no budget            (a stop would be invisible)
#   - a budget under MIN_RATIO_PCT% of the cron interval    (false-fires on every normal run)
#   - a budget on a STOPPED schedule                        (DagsterJobNeverRan/Stale would page forever for a job
#                                                            that is off by design)
#   - a budget naming a job with no schedule                (deleted or renamed — the watch watches nothing)
#
# FAILS CLOSED (exit 2): no Definitions(schedules=[...]) found, a listed schedule the parser cannot resolve (a new
# factory shape must be taught here, never skipped), no BUDGETS block, or a cron shape with no modelled period.
#
# The code default_status is what this reads. A schedule toggled in the UI can differ from it; that drift is why the
# six mismatched defaults were corrected in code on 2026-09-27 (code = live) rather than listed as exceptions here.
#
#   usage: scripts/check-dagster-watchdog-budgets.sh [--list]
#          --list   print the per-schedule table and exit 0 (reporting, not gating)
set -uo pipefail

. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

PIPELINE_DIR="${DAGSTER_PIPELINE_DIR:-$PLATFORM_DIR/services/weyland-dagster/weyland_pipeline}"
MANIFEST="${DAGSTER_WATCHDOG_MANIFEST:-$PLATFORM_DIR/k8s/dagster/freshness.yaml}"
# The factory's job naming is single-sourced in this Dagster-free module; the guard loads it rather than re-encoding
# the f-string, so a rename there cannot silently desynchronise the guard.
DOMAIN_JOB_PLAN="${DAGSTER_DOMAIN_JOB_PLAN:-$PLATFORM_DIR/services/weyland-dagster/weyland_pipeline/assets/datasets_lib/domain_job_plan.py}"

# Budget floor as a percentage of the cron interval. 110%, chosen from the DEPLOYED budgets: daily 30h is 125% and
# weekly 8d is 114%. A floor at the ~125% the manifest comment aims for would reject the weekly budgets that have
# never false-fired, which is how a guard trains people to widen numbers to satisfy it. 110% still fails every
# drift actually seen (8h on a daily job is 33%).
MIN_RATIO_PCT="${DAGSTER_BUDGET_MIN_PCT:-110}"

# cron_period_seconds — reuse the CronJob guard's classifier (same repo cron shapes, same refusal of unknown ones).
CRON_BUDGETS_LIB=1 . "$(dirname "${BASH_SOURCE[0]}")/check-cron-freshness-budgets.sh"
set +e

# Emit `job<TAB>cron<TAB>status` per schedule in Definitions(schedules=[...]), or `UNRESOLVED<TAB>name` /
# `NO-DEFINITIONS`. Pure AST — no dagster import, so it runs in the repo-guards image.
schedules_from_code() {
  python3 - "$PIPELINE_DIR" "$DOMAIN_JOB_PLAN" <<'PY'
import ast, importlib.util, os, sys

root, plan_path = sys.argv[1], sys.argv[2]
plan = None
if os.path.isfile(plan_path):
    spec = importlib.util.spec_from_file_location("domain_job_plan", plan_path)
    plan = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(plan)

jobs, scheds, factories, cfg_domain, listed = {}, {}, {}, {}, None


def call_name(node):
    f = node.func
    return f.id if isinstance(f, ast.Name) else f.attr if isinstance(f, ast.Attribute) else None


def kw(node, name):
    return next((k.value for k in node.keywords if k.arg == name), None)


def const(node):
    return node.value if isinstance(node, ast.Constant) else None


def status(node):
    # Dagster's own default for a ScheduleDefinition with no default_status is STOPPED.
    return node.attr if isinstance(node, ast.Attribute) else "STOPPED"


for dirpath, dirs, files in os.walk(root):
    dirs[:] = [d for d in dirs if d not in ("tests", "__pycache__")]
    for fn in files:
        if not fn.endswith(".py"):
            continue
        tree = ast.parse(open(os.path.join(dirpath, fn), encoding="utf-8").read())
        for node in ast.walk(tree):
            if isinstance(node, ast.FunctionDef):
                for dec in node.decorator_list:
                    target = dec.func if isinstance(dec, ast.Call) else dec
                    if isinstance(target, ast.Name) and target.id in ("job", "graph_job"):
                        named = const(kw(dec, "name")) if isinstance(dec, ast.Call) else None
                        jobs[node.name] = named or node.name
            if isinstance(node, ast.Call) and call_name(node) == "Definitions":
                s = kw(node, "schedules")
                if isinstance(s, (ast.List, ast.Tuple)):
                    listed = [e.id if isinstance(e, ast.Name) else ast.unparse(e) for e in s.elts]
            if not (isinstance(node, ast.Assign) and len(node.targets) == 1 and isinstance(node.value, ast.Call)
                    or isinstance(node, ast.Assign) and isinstance(node.value, ast.Attribute)):
                continue
            target = node.targets[0]
            if not isinstance(target, ast.Name):
                continue
            v, name = node.value, target.id
            if isinstance(v, ast.Attribute):
                if v.attr == "land_schedule" and isinstance(v.value, ast.Name):
                    scheds[name] = ("FACTORY", v.value.id)
                continue
            cn = call_name(v)
            if cn == "define_asset_job":
                jobs[name] = const(kw(v, "name")) or (const(v.args[0]) if v.args else None)
            elif cn == "ScheduleDefinition":
                j = kw(v, "job")
                scheds[name] = ("DIRECT", j.id if isinstance(j, ast.Name) else None,
                                const(kw(v, "cron_schedule")), status(kw(v, "default_status")))
            elif cn == "build_domain_jobs":
                cfg = v.args[0].id if v.args and isinstance(v.args[0], ast.Name) else None
                factories[name] = (cfg, const(kw(v, "land_cron")), status(kw(v, "land_status")))
            elif cn == "DomainConfig":
                cfg_domain[name] = const(kw(v, "domain"))

if listed is None:
    print("NO-DEFINITIONS")
    sys.exit(0)
for s in listed:
    entry = scheds.get(s)
    row = None
    if entry and entry[0] == "DIRECT":
        _, jv, cron, st = entry
        if jobs.get(jv) and cron:
            row = (jobs[jv], cron, st)
    elif entry and entry[0] == "FACTORY" and plan is not None:
        f = factories.get(entry[1])
        if f and f[1] and cfg_domain.get(f[0]):
            p = plan.domain_job_plan(cfg_domain[f[0]], "", ())
            row = (p["land"]["name"], f[1], f[2])
    print("\t".join(row) if row else f"UNRESOLVED\t{s}")
PY
}

# Emit `job<TAB>seconds` for every row of the watchdog's BUDGETS block, or NO-BUDGETS.
budgets_from_manifest() {
  python3 - "$MANIFEST" <<'PY'
import re, sys
text = open(sys.argv[1], encoding="utf-8").read()
m = re.search(r"BUDGETS=\$\(cat <<'BUDGETS_EOF'\n(.*?)\n\s*BUDGETS_EOF", text, re.S)
rows = [l.split("#")[0].split() for l in m.group(1).splitlines()] if m else []
rows = [r for r in rows if r]
if not rows:
    print("NO-BUDGETS")
for r in rows:
    print(f"{r[0]}\t{r[1]}")
PY
}

main() {
  local list_only=0
  [ "${1-}" = "--list" ] && list_only=1

  command -v python3 >/dev/null 2>&1 || { echo "❌ python3 not found on PATH" >&2; exit 2; }
  [ -d "$PIPELINE_DIR" ] || { echo "❌ pipeline dir missing: $PIPELINE_DIR" >&2; exit 2; }
  [ -f "$MANIFEST" ]     || { echo "❌ watchdog manifest missing: $MANIFEST" >&2; exit 2; }

  local scheds budgets
  scheds="$(schedules_from_code)" || { echo "❌ could not parse the pipeline under $PIPELINE_DIR" >&2; exit 2; }
  budgets="$(budgets_from_manifest)" || { echo "❌ could not read $MANIFEST" >&2; exit 2; }

  # Verifying NOTHING is not verifying successfully.
  if [ -z "$scheds" ] || [ "$scheds" = "NO-DEFINITIONS" ]; then
    echo "❌ no Definitions(schedules=[...]) found under $PIPELINE_DIR — refusing to report OK" >&2; exit 2
  fi
  if grep -q '^UNRESOLVED' <<<"$scheds"; then
    echo "❌ listed schedule(s) the guard cannot resolve to a job + cron — teach it the shape, never skip:" >&2
    grep '^UNRESOLVED' <<<"$scheds" | cut -f2 | sed 's/^/     /' >&2; exit 2
  fi
  if [ "$budgets" = "NO-BUDGETS" ]; then
    echo "❌ no BUDGETS block parsed from $MANIFEST — refusing to report OK" >&2; exit 2
  fi

  local fail=0 cantrun=0 nbudget=0 job cron st budget period
  printf '%-40s %-14s %-8s %-8s %s\n' "JOB" "CRON" "STATUS" "PERIOD" "BUDGET"
  while IFS=$'\t' read -r job cron st; do
    budget="$(awk -F'\t' -v j="$job" '$1==j {print $2; exit}' <<<"$budgets")"
    if ! period="$(cron_period_seconds "$cron" 2>&1)"; then
      echo "  ❌ ${job}: cannot derive an interval from '${cron}' (${period})" >&2; cantrun=1; continue
    fi
    printf '%-40s %-14s %-8s %-8s %s\n' "$job" "$cron" "$st" "${period}s" "${budget:-none}"
    if [ "$st" = "RUNNING" ] && [ -z "$budget" ]; then
      echo "  ❌ ${job}: schedule is RUNNING with no budget in the watchdog — a stop would be invisible" >&2; fail=1
    elif [ "$st" != "RUNNING" ] && [ -n "$budget" ]; then
      echo "  ❌ ${job}: schedule is ${st} but the watchdog budgets it — it would page forever for a job off by design" >&2; fail=1
    elif [ -n "$budget" ]; then
      nbudget=$((nbudget + 1))
      if [ $((budget * 100)) -lt $((period * MIN_RATIO_PCT)) ]; then
        echo "  ❌ ${job}: budget ${budget}s is under ${MIN_RATIO_PCT}% of its interval ${period}s — false-fires every run" >&2; fail=1
      fi
    fi
  done <<<"$scheds"

  while IFS=$'\t' read -r job budget; do
    [ -n "$job" ] || continue
    if ! cut -f1 <<<"$scheds" | grep -qx "$job"; then
      echo "  ❌ ${job}: budgeted in the watchdog but has no schedule (deleted or renamed job)" >&2; fail=1
    fi
  done <<<"$budgets"

  [ "$list_only" -eq 1 ] && return 0
  [ "$cantrun" -eq 0 ] || { echo "❌ could not model every schedule's interval — refusing to report OK" >&2; exit 2; }
  if [ "$fail" -ne 0 ]; then
    echo >&2
    echo "❌ Dagster watchdog budgets disagree with the schedules. Fix the BUDGETS block in k8s/dagster/freshness.yaml" >&2
    echo "   or the ScheduleDefinition's default_status." >&2
    exit 1
  fi
  echo "OK — $(grep -c . <<<"$scheds") schedule(s), ${nbudget} budgeted: every RUNNING schedule is watched within budget."
}

main "$@"
