#!/usr/bin/env bats
# Guard for the cadence fact that lives on THREE surfaces (B140, found grading DoD Pillar 8):
# a CronJob's manifest `schedule:`, its row in docs/schedules.md, and its budget in the
# cron-freshness PrometheusRule. Nothing kept them honest, so changing a schedule silently
# broke the alert — tighten a job and its 26h budget stops catching a stop; relax one and it
# false-fires every week, which is the WeylandErrorLogSpike failure (a permanently-lit alert
# is worse than none).
#
# The guard exposes its decision helpers for testing via CRON_BUDGETS_LIB=1, the same
# arrangement as ship-images.sh and the ConfigMap-backed watchdogs.

setup() {
  load helper
  setup_stubs
  GUARD="$REPO_ROOT/scripts/check-cron-freshness-budgets.sh"
}

teardown() {
  teardown_stubs
}

@test "the guard exists and is executable" {
  [ -x "$GUARD" ]
}

# --- period classifier -------------------------------------------------------------------
# Real cron shapes in this repo only. It does NOT need general cron math, but it MUST refuse
# anything it does not understand rather than guessing a period.

@test "period: step-in-minutes (*/30 * * * *) is 30 minutes" {
  CRON_BUDGETS_LIB=1 source "$GUARD"
  run cron_period_seconds '*/30 * * * *'
  [ "$status" -eq 0 ]
  [ "$output" -eq 1800 ]
}

@test "period: step-in-hours (0 */6 * * *) is 6 hours" {
  CRON_BUDGETS_LIB=1 source "$GUARD"
  run cron_period_seconds '0 */6 * * *'
  [ "$status" -eq 0 ]
  [ "$output" -eq 21600 ]
}

@test "period: a fixed time with no day-of-week is daily" {
  CRON_BUDGETS_LIB=1 source "$GUARD"
  run cron_period_seconds '30 22 * * *'
  [ "$status" -eq 0 ]
  [ "$output" -eq 86400 ]
}

@test "period: a day-of-week constraint makes it weekly" {
  CRON_BUDGETS_LIB=1 source "$GUARD"
  run cron_period_seconds '0 12 * * 0'
  [ "$status" -eq 0 ]
  [ "$output" -eq 604800 ]
}

@test "period: an UNRECOGNISED schedule FAILS CLOSED rather than guessing" {
  # The whole point. A classifier that quietly returns a default when it cannot parse is the
  # same bug this guard exists to prevent — three separate instances of it were found in this
  # effort alone. Refusing loudly is the only safe behaviour.
  CRON_BUDGETS_LIB=1 source "$GUARD"
  run cron_period_seconds '5 4 1 * *'          # day-of-month — monthly, not handled
  [ "$status" -ne 0 ]
  [[ "$output" == *"unrecognised"* || "$output" == *"cannot"* ]]
  run cron_period_seconds '@daily'
  [ "$status" -ne 0 ]
  run cron_period_seconds ''
  [ "$status" -ne 0 ]
}

# --- budget adequacy ---------------------------------------------------------------------

@test "budget: a budget comfortably above the period passes" {
  CRON_BUDGETS_LIB=1 source "$GUARD"
  run budget_ok 86400 93600      # daily job, 26h budget
  [ "$status" -eq 0 ]
}

@test "budget: a budget BELOW the period fails — it could never catch a stop" {
  CRON_BUDGETS_LIB=1 source "$GUARD"
  run budget_ok 604800 93600     # weekly job wrongly given the 26h daily budget
  [ "$status" -ne 0 ]
}

@test "budget: a budget only barely above the period fails the slack requirement" {
  # A budget equal to (or a whisker above) the period alerts on every normal late run.
  CRON_BUDGETS_LIB=1 source "$GUARD"
  run budget_ok 86400 86460      # 24h + 1 min
  [ "$status" -ne 0 ]
}

# --- end-to-end against the real repo ----------------------------------------------------

@test "the repo currently passes the guard" {
  run "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK"* ]]
}

@test "the guard NAMES a CronJob covered by no freshness rule" {
  # This is the check that would have caught cron-freshness-check missing from its own rule —
  # the bug found by hand while grading DoD Pillar 8.
  run "$GUARD" --list
  [ "$status" -eq 0 ]
  [[ "$output" == *"cron-freshness-check"* ]]
}

# --- FAILURE-side coverage (B140) --------------------------------------------------------
#
# Freshness answers "did it stop?" — `time() - last_successful_time > budget`. It is structurally
# blind to a job that RAN AND FAILED and then succeeded inside its budget, because the success
# timestamp advances and the rule goes quiet.
#
# Evidence this is not theoretical: `dagster-freshness-check-29791170` sat `Failed` in ns weyland
# for 19 HOURS. Later runs succeeded, so freshness stayed green and nothing alerted. By the time
# anyone noticed, the pod and its events had aged out and the cause was unrecoverable.
#
# The estate had exactly ONE failure-side rule — `DataMeshBackupFailed` — and it was half broken:
# its regex `job_name=~"(minio|pg)-backup.*"` reads as covering both, while the namespace selector
# one line above pinned it to `data-mesh`. `minio-backup` lives in namespace `minio`, so a failing
# MinIO backup (the mlflow + tofu-state buckets — irreplaceable) alerted NOBODY.

@test "the guard reads its rule file from an overridable path" {
  # Needed so the negative cases below can point at a crafted rule file instead of the repo's.
  #
  # This asserts the override is HONOURED, not merely accepted: pointing it at a rule file with no
  # rules must make the guard refuse. Asserting that a copy of the real file still passes would be
  # vacuous — it passes identically when the override is ignored.
  printf 'apiVersion: monitoring.coreos.com/v1\nkind: PrometheusRule\nmetadata:\n  name: empty\nspec:\n  groups: []\n' \
    > "$STUB_DIR/empty.yaml"
  CRON_RULES_FILE="$STUB_DIR/empty.yaml" run "$GUARD"
  [ "$status" -ne 0 ]
  [[ "$output" == *"refusing"* ]]
}

@test "the guard FAILS and NAMES a CronJob covered by no FAILURE rule" {
  # Drop ONLY the backup rule, leaving ScheduledJobFailed in place. That is the realistic drift —
  # someone adds a CronJob, or deletes one rule, and the rest still parse. Stripping *every* failure
  # rule instead trips the earlier "refusing to report OK" guard, which is also correct but proves
  # something different: this case has to reach the per-job table and NAME the uncovered job.
  python3 - "$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s/monitoring/cron-freshness-rules.yaml" "$STUB_DIR/nobackup.yaml" <<'PY'
import sys, yaml
d = yaml.safe_load(open(sys.argv[1]))
for g in d["spec"]["groups"]:
    g["rules"] = [r for r in g["rules"] if r.get("alert") != "ScheduledBackupFailed"]
yaml.safe_dump(d, open(sys.argv[2], "w"))
PY
  CRON_RULES_FILE="$STUB_DIR/nobackup.yaml" run "$GUARD"
  [ "$status" -ne 0 ]
  # All three backups must be named, not just whichever one is listed first.
  [[ "$output" == *"minio-backup"* ]]
  [[ "$output" == *"pg-backup"* ]]
  [[ "$output" == *"postgres-backup"* ]]
  [[ "$output" == *"NO failure rule"* ]]
}

@test "the guard FAILS when a CronJob is covered by TWO failure rules — one break, two pages" {
  # Duplicate coverage is not harmless: it double-pages, and duplicate pages are how an on-call
  # learns to ignore a rule. Add the backups to ScheduledJobFailed as well, so each is named twice.
  python3 - "$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s/monitoring/cron-freshness-rules.yaml" "$STUB_DIR/dupe.yaml" <<'PY'
import sys, yaml, re
d = yaml.safe_load(open(sys.argv[1]))
for g in d["spec"]["groups"]:
    for r in g["rules"]:
        if r.get("alert") == "ScheduledJobFailed":
            r["expr"] = re.sub(r'job_name=~"\(', 'job_name=~"(minio-backup|', r["expr"], count=1)
yaml.safe_dump(d, open(sys.argv[2], "w"))
PY
  CRON_RULES_FILE="$STUB_DIR/dupe.yaml" run "$GUARD"
  [ "$status" -ne 0 ]
  [[ "$output" == *"minio-backup"* ]]
  [[ "$output" == *"2 failure rules"* ]]
}

@test "every CronJob in the repo has BOTH a freshness and a failure rule" {
  run "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK"* ]]
}

@test "the backup CronJobs are covered, including the one in the minio namespace" {
  # The exact gap DataMeshBackupFailed left: minio-backup is in ns `minio`, not `data-mesh`.
  run "$GUARD" --list
  [ "$status" -eq 0 ]
  [[ "$output" == *"minio-backup"* ]]
}
