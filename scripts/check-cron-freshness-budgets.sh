#!/usr/bin/env bash
# Cron freshness-budget drift guard (B140). Asserts that the three surfaces carrying a
# CronJob's cadence agree:
#
#   1. the manifest `schedule:`            — the TRUTH (what the cluster actually does)
#   2. k8s/monitoring/cron-freshness-rules.yaml — the alert budget derived from it
#   3. docs/schedules.md                   — the documented timetable
#
# WHY THIS EXISTS: found 2026-08-23 while grading DoD Pillar 8 (cascading changes) on B135.
# The freshness rule this repo had just gained re-encodes every job's cadence by hand, and
# nothing kept it honest afterwards. Change a schedule and the budget silently goes wrong in
# one of two ways, both bad:
#   - TIGHTEN a job (daily -> hourly) and its 26h budget stops catching a stop entirely.
#   - RELAX a job (daily -> weekly) and the budget false-fires every single week. A
#     permanently-lit alert is worse than no alert — exactly what WeylandErrorLogSpike was
#     found doing on 2026-08-22, matching `NOERROR` with /error/.
#
# It also catches the two failures that motivated the whole watchdog effort:
#   - a CronJob covered by NO rule (cron-freshness-check was missing from its own rule —
#     found by hand while grading Pillar 8, which is not a repeatable control)
#   - a CronJob with no row in docs/schedules.md (three backup CronJobs were undocumented AND
#     running on the wrong clock; found only because a human ran the reconciliation)
#
# FAILS CLOSED, deliberately. An unparseable schedule, an unknown cron shape, or a missing
# input is a loud error — never a skip. A guard that quietly passes when it cannot read
# something is the same class of bug it exists to prevent, and this effort produced three
# separate instances of exactly that (woodpecker-cli --output json, curl -sf, promtool exit 0).
#
#   usage: scripts/check-cron-freshness-budgets.sh [--list]
#          --list   print the per-CronJob table and exit 0 (reporting, not gating)
#
# Sourced by scripts/tests/cron-freshness-budgets.bats with CRON_BUDGETS_LIB=1 to exercise the
# decision helpers directly; everything above main() is therefore side-effect free.
set -euo pipefail

. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

RULES="$PLATFORM_DIR/k8s/monitoring/cron-freshness-rules.yaml"
K8S_DIR="$PLATFORM_DIR/k8s"
SCHEDULES="$REPO_ROOT/docs/schedules.md"

# Minimum slack over the job's own period before a budget is considered usable. A budget equal
# to (or a whisker above) the period alerts on every normal late run, which is the false-positive
# half of the failure this guard defends against.
#
# 5% is chosen from the DEPLOYED budgets, not invented: the real slacks are 300% (30m job / 2h),
# 33% (6h / 8h), 14% (weekly / 8d) and — the tightest — 8.3% (daily 24h / 26h). A floor above
# 8.3% would reject the repo's own sensible daily budget, which is how a guard trains people to
# widen numbers to satisfy it instead of to reflect reality. 5% still fails "budget == period"
# (the case that matters) while leaving every real budget comfortably clear.
SLACK_FRACTION="${CRON_BUDGET_SLACK:-5}"

# cron_period_seconds <five-field-cron> -> seconds on stdout, non-zero + message on stderr.
#
# Deliberately NOT general cron math. It understands only the shapes this repo actually uses
# and REFUSES everything else, because a wrong period silently produces a wrong budget.
cron_period_seconds() {
  local expr="${1-}"
  local min hour dom mon dow
  read -r min hour dom mon dow <<<"$expr" || true
  if [ -z "${min:-}" ] || [ -z "${hour:-}" ] || [ -z "${dom:-}" ] || [ -z "${mon:-}" ] || [ -z "${dow:-}" ]; then
    echo "cannot parse schedule (expected five fields): '${expr}'" >&2; return 1
  fi
  # Day-of-month or month constraints mean monthly/yearly cadences we do not model.
  if [ "$dom" != "*" ] || [ "$mon" != "*" ]; then
    echo "unrecognised schedule (day-of-month/month constraint not modelled): '${expr}'" >&2; return 1
  fi
  case "$min" in
    \*/[0-9]*)
      [ "$hour" = "*" ] || { echo "unrecognised schedule (minute step with hour constraint): '${expr}'" >&2; return 1; }
      echo $(( ${min#*/} * 60 )); return 0 ;;
  esac
  case "$hour" in
    \*/[0-9]*)
      echo $(( ${hour#*/} * 3600 )); return 0 ;;
  esac
  # Fixed minute + fixed hour from here on.
  case "$min$hour" in
    *[!0-9]*) echo "unrecognised schedule (non-numeric minute/hour): '${expr}'" >&2; return 1 ;;
  esac
  if [ "$dow" = "*" ]; then echo 86400; return 0; fi
  case "$dow" in
    *[!0-9]*) echo "unrecognised schedule (non-numeric day-of-week): '${expr}'" >&2; return 1 ;;
  esac
  echo 604800; return 0
}

# budget_ok <period-seconds> <budget-seconds> — budget must exceed the period by SLACK_FRACTION%.
budget_ok() {
  local period="${1:?}" budget="${2:?}"
  local need=$(( period + (period * SLACK_FRACTION / 100) ))
  [ "$budget" -ge "$need" ]
}

# Emit `name<TAB>schedule<TAB>timezone` for every CronJob manifest in the k8s tree.
cronjobs_from_manifests() {
  python3 - "$K8S_DIR" <<'PY'
import sys, os, yaml
root = sys.argv[1]
for dirpath, _, files in os.walk(root):
    for fn in files:
        if not fn.endswith((".yaml", ".yml")):
            continue
        p = os.path.join(dirpath, fn)
        try:
            docs = list(yaml.safe_load_all(open(p, encoding="utf-8", errors="replace")))
        except Exception:
            continue
        for d in docs:
            if isinstance(d, dict) and d.get("kind") == "CronJob":
                n = (d.get("metadata") or {}).get("name")
                s = (d.get("spec") or {}).get("schedule")
                tz = (d.get("spec") or {}).get("timeZone") or ""
                if n and s:
                    print(f"{n}\t{s}\t{tz}")
PY
}

# Emit `cronjob-name<TAB>budget-seconds` for every job named by a ScheduledJobStale rule.
budgets_from_rules() {
  python3 - "$RULES" <<'PY'
import sys, re, yaml
d = yaml.safe_load(open(sys.argv[1], encoding="utf-8"))
for g in (d.get("spec", {}).get("groups") or []):
    for r in (g.get("rules") or []):
        if r.get("alert") != "ScheduledJobStale":
            continue
        expr = r.get("expr") or ""
        m = re.search(r'cronjob\s*=~?\s*"([^"]+)"', expr)
        thr = re.search(r'>\s*(\d+)', expr)
        if not m or not thr:
            print("PARSE-FAIL\t" + expr.strip().replace("\n", " ")[:80]); continue
        for name in m.group(1).split("|"):
            print(f"{name}\t{thr.group(1)}")
PY
}

main() {
  local list_only=0
  [ "${1-}" = "--list" ] && list_only=1

  command -v python3 >/dev/null 2>&1 || { echo "❌ python3 not found on PATH" >&2; exit 1; }
  [ -f "$RULES" ]     || { echo "❌ rule file missing: $RULES" >&2; exit 1; }
  [ -f "$SCHEDULES" ] || { echo "❌ schedules doc missing: $SCHEDULES" >&2; exit 1; }

  local jobs budgets
  jobs="$(cronjobs_from_manifests)"
  budgets="$(budgets_from_rules)"

  # Verifying NOTHING is not verifying successfully.
  [ -n "$jobs" ]    || { echo "❌ no CronJob manifests found under $K8S_DIR — refusing to report OK" >&2; exit 1; }
  [ -n "$budgets" ] || { echo "❌ no ScheduledJobStale rules parsed from $RULES — refusing to report OK" >&2; exit 1; }
  if grep -q '^PARSE-FAIL' <<<"$budgets"; then
    echo "❌ could not parse a ScheduledJobStale expr (cronjob matcher + threshold expected):" >&2
    grep '^PARSE-FAIL' <<<"$budgets" >&2; exit 1
  fi

  local fail=0 checked=0 name sched tz period budget row
  printf '%-26s %-16s %-10s %-10s %s\n' "CRONJOB" "SCHEDULE" "PERIOD" "BUDGET" "SCHEDULES.MD"
  while IFS=$'\t' read -r name sched tz; do
    [ -n "$name" ] || continue
    checked=$((checked + 1))

    if ! period="$(cron_period_seconds "$sched")"; then
      echo "  ❌ ${name}: ${sched} — cannot derive a period" >&2; fail=1; continue
    fi

    budget="$(awk -F'\t' -v n="$name" '$1==n {print $2; exit}' <<<"$budgets")"
    row="missing"; grep -qF "\`${name}\`" "$SCHEDULES" && row="ok"

    printf '%-26s %-16s %-10s %-10s %s\n' \
      "$name" "$sched" "${period}s" "${budget:-NONE}" "$row"

    if [ -z "$budget" ]; then
      echo "  ❌ ${name} is covered by NO ScheduledJobStale rule — a stop would be invisible" >&2; fail=1
    elif ! budget_ok "$period" "$budget"; then
      echo "  ❌ ${name}: budget ${budget}s is not ≥ period ${period}s + ${SLACK_FRACTION}% slack" >&2; fail=1
    fi
    if [ "$row" != "ok" ]; then
      echo "  ❌ ${name} has no row in docs/schedules.md — an undocumented timer is drift" >&2; fail=1
    fi

    # A k8s CronJob with no `spec.timeZone` runs in the kube-controller-manager's clock (UTC),
    # NOT local time — schedules.md Design Rule #1 requires it be set explicitly. This is not
    # theoretical: minio-backup / pg-backup / postgres-backup each carried a "# 02:30 local"
    # style comment while actually firing at 22:30-23:30 NY, undetected until a human ran the
    # reconciliation by hand on 2026-08-23.
    #
    # Only fixed-time schedules are gated. A step schedule (*/30, */6) fires at the same
    # interval in every timezone, so a missing timeZone there changes nothing and failing it
    # would be noise — the kind that teaches people to silence a guard.
    if [ -z "$tz" ] && [ "$period" -ge 86400 ]; then
      echo "  ❌ ${name} sets no spec.timeZone — a fixed-time schedule then runs in UTC, not NY (Design Rule #1)" >&2
      fail=1
    fi
  done <<<"$jobs"

  [ "$list_only" -eq 1 ] && return 0

  if [ "$fail" -ne 0 ]; then
    echo >&2
    echo "❌ cron freshness budgets disagree with the manifests (${checked} CronJob(s) checked)." >&2
    echo "   Fix the budget in k8s/monitoring/cron-freshness-rules.yaml, or the row in docs/schedules.md." >&2
    exit 1
  fi
  echo "OK — ${checked} CronJob(s): every one has a freshness rule with adequate budget and a schedules.md row."
}

if [ -z "${CRON_BUDGETS_LIB:-}" ]; then
  main "$@"
fi
