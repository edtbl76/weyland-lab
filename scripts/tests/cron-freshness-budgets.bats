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
