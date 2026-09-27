#!/usr/bin/env bats
# B196 — the Dagster watchdog's per-job budgets (k8s/dagster/freshness.yaml) re-encode every schedule's cadence by
# hand, and nothing kept them honest. Found shipping B194 (2026-09-27):
#   - weyland_catalog_job / weyland_timeseries_job / datahub_catalog_emit_job went nightly on 2026-08-07 but kept
#     6-8h budgets, so for seven weeks they false-fired DagsterJobStale every 30 minutes;
#   - feast_materialize_job (daily) and registrations_reconcile_job (weekly) ran with NO budget at all, so a stop
#     was invisible;
#   - six schedules' code default_status disagreed with their live state.
# check-cron-freshness-budgets.sh covers k8s CronJobs only; this is its Dagster sibling.
#
# Every fixture is built per test so each rule is proven to FAIL for its own named reason — a guard whose only
# end-to-end test is "the real repo passes" cannot fail for the right reason.

setup() {
  load helper
  setup_stubs
  GUARD="$REPO_ROOT/scripts/check-dagster-watchdog-budgets.sh"
  PIPE="$STUB_DIR/pipe"
  mkdir -p "$PIPE"
  export DAGSTER_PIPELINE_DIR="$PIPE"
  export DAGSTER_WATCHDOG_MANIFEST="$STUB_DIR/freshness.yaml"
}

teardown() {
  teardown_stubs
}

# pipe_defs <python-source> — the fixture pipeline package (one module is enough; the guard walks every .py).
pipe_defs() {
  printf '%s\n' "$1" >"$PIPE/definitions.py"
}

# watch_budgets <"job seconds" lines> — a watchdog manifest carrying exactly these budgets.
watch_budgets() {
  cat >"$DAGSTER_WATCHDOG_MANIFEST" <<EOF
apiVersion: batch/v1
kind: CronJob
metadata:
  name: dagster-freshness-check
spec:
  jobTemplate:
    spec:
      template:
        spec:
          containers:
            - name: check
              args:
                - |
                  BUDGETS=\$(cat <<'BUDGETS_EOF'
$(printf '%s\n' "$1" | sed 's/^/                  /')
                  BUDGETS_EOF
                  )
EOF
}

# A healthy two-schedule pipeline: one daily RUNNING, one weekly RUNNING, one STOPPED (unbudgeted, correctly).
HEALTHY_DEFS='
from dagster import ScheduleDefinition, DefaultScheduleStatus, Definitions, define_asset_job, job

daily_job = define_asset_job(name="daily_job", selection="x")

@job
def weekly_op_job():
    pass

daily_schedule = ScheduleDefinition(job=daily_job, cron_schedule="17 2 * * *",
                                    default_status=DefaultScheduleStatus.RUNNING)
weekly_schedule = ScheduleDefinition(job=weekly_op_job, cron_schedule="0 5 * * 0",
                                     default_status=DefaultScheduleStatus.RUNNING)
off_job = define_asset_job("off_job", selection="y")
off_schedule = ScheduleDefinition(job=off_job, cron_schedule="0 4 * * *")

defs = Definitions(schedules=[daily_schedule, weekly_schedule, off_schedule])
'
HEALTHY_BUDGETS='daily_job 108000  # daily -> 30h
weekly_op_job 691200  # weekly -> 8d'

@test "the guard exists and is executable" {
  [ -x "$GUARD" ]
}

@test "a pipeline whose budgets match its RUNNING schedules passes" {
  pipe_defs "$HEALTHY_DEFS"
  watch_budgets "$HEALTHY_BUDGETS"
  run bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK"* ]]
  [[ "$output" == *"2 budgeted"* ]]
}

@test "a RUNNING schedule with no budget fails, naming the job" {
  pipe_defs "$HEALTHY_DEFS"
  watch_budgets 'daily_job 108000'
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"weekly_op_job"*"RUNNING"*"no budget"* ]]
}

@test "a budget shorter than the schedule interval fails (the 2026-08-07 drift)" {
  pipe_defs "$HEALTHY_DEFS"
  watch_budgets 'daily_job 28800
weekly_op_job 691200'
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"daily_job"*"28800"*"86400"* ]]
}

@test "a budget naming a job with no schedule fails (deleted or renamed job)" {
  pipe_defs "$HEALTHY_DEFS"
  watch_budgets "$HEALTHY_BUDGETS
ghost_job 108000"
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"ghost_job"*"no schedule"* ]]
}

@test "a budget on a STOPPED schedule fails — it would page forever for a job that is off by design" {
  pipe_defs "$HEALTHY_DEFS"
  watch_budgets "$HEALTHY_BUDGETS
off_job 108000"
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"off_job"*"STOPPED"* ]]
}

@test "a schedule with no default_status is STOPPED (Dagster's own default), so it needs no budget" {
  pipe_defs "$HEALTHY_DEFS"
  watch_budgets "$HEALTHY_BUDGETS"
  run bash "$GUARD" --list
  [ "$status" -eq 0 ]
  [[ "$output" == *"off_job"*"STOPPED"* ]]
}

@test "a factory-built land schedule (build_domain_jobs) is seen with its derived job name" {
  pipe_defs "$HEALTHY_DEFS"
  cat >>"$PIPE/definitions.py" <<'PY'
from x import build_domain_jobs, DomainConfig, DefaultScheduleStatus
FIN_CFG = DomainConfig(domain="finance", repo="finance")
_fin = build_domain_jobs(FIN_CFG, serial_exec={}, hydrate_exec={}, land_cron="50 4 * * *",
                         land_status=DefaultScheduleStatus.RUNNING)
fin_land_schedule = _fin.land_schedule
defs = Definitions(schedules=[daily_schedule, weekly_schedule, off_schedule, fin_land_schedule])
PY
  watch_budgets "$HEALTHY_BUDGETS"
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"weyland_datasets_finance_land_job"*"RUNNING"*"no budget"* ]]
}

@test "a listed schedule the parser cannot resolve is exit 2, never a pass" {
  pipe_defs "$HEALTHY_DEFS
mystery_schedule = make_schedule_somehow()
defs = Definitions(schedules=[daily_schedule, weekly_schedule, off_schedule, mystery_schedule])"
  watch_budgets "$HEALTHY_BUDGETS"
  run bash "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"mystery_schedule"* ]]
}

@test "no Definitions(schedules=...) found is exit 2 — verifying nothing is not verifying" {
  pipe_defs 'x = 1'
  watch_budgets "$HEALTHY_BUDGETS"
  run bash "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"Definitions"* ]]
}

@test "a manifest with no BUDGETS block is exit 2" {
  pipe_defs "$HEALTHY_DEFS"
  printf 'kind: CronJob\n' >"$DAGSTER_WATCHDOG_MANIFEST"
  run bash "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"BUDGETS"* ]]
}

@test "an unmodelled cron shape (monthly) is exit 2, not a guessed period" {
  pipe_defs "${HEALTHY_DEFS/0 5 \* \* 0/0 5 1 * *}"
  watch_budgets "$HEALTHY_BUDGETS"
  run bash "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"weekly_op_job"* ]]
}

# --- the real repo ------------------------------------------------------------------------------------------------

@test "the real pipeline and watchdog agree" {
  unset DAGSTER_PIPELINE_DIR DAGSTER_WATCHDOG_MANIFEST
  run bash "$GUARD"
  [ "$status" -eq 0 ]
}

@test "reverting the 2026-09-27 catalog fix (30h -> 8h) fails naming weyland_catalog_job" {
  unset DAGSTER_PIPELINE_DIR
  real="$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s/dagster/freshness.yaml"
  sed -E 's/^( *weyland_catalog_job +)108000/\128800/' "$real" >"$DAGSTER_WATCHDOG_MANIFEST"
  ! cmp -s "$real" "$DAGSTER_WATCHDOG_MANIFEST"   # tripwire: the sed must actually have changed something
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"weyland_catalog_job"* ]]
}
