#!/usr/bin/env bats
# B94/B196 — the Dagster per-job watchdog (k8s/dagster/freshness.yaml). The logic under test is the exact shell the
# CronJob runs, pulled back out of the manifest: a tested copy beside a deployed copy drifts silently while both
# halves keep passing their own checks (the pr-staleness / cron-freshness arrangement).
#
# B196 adds the case the original could not see: a budgeted job with NO row in `runs` never appeared in the query's
# output, so it could never alert. B194's linear_backup_job sat exactly there until its first scheduled run — the
# same absence-as-success class as B135's `absent()`.

setup() {
  load helper
  setup_stubs
  MANIFEST="$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s/dagster/freshness.yaml"
  LOGIC="$STUB_DIR/dagster-freshness.sh"
  python3 - "$MANIFEST" >"$LOGIC" <<'PY'
import sys, yaml
d = yaml.safe_load(open(sys.argv[1]))
print(d["spec"]["jobTemplate"]["spec"]["template"]["spec"]["containers"][0]["args"][0])
PY
  export JOBS_FILE="$STUB_DIR/jobs.txt"
  stub wget 0 ''
  BUDGETED="$(awk '/^BUDGETS=/{f=1;next} /^BUDGETS_EOF/{f=0} f && $1 !~ /^#/ && NF {print $1}' "$LOGIC")"
}

teardown() {
  teardown_stubs
}

# rows <overrides...> — a psql result with a healthy fresh SUCCESS row for every budgeted job, then each
# `job|STATUS|age` override replacing that job's row (or adding it).
rows() {
  local out="" j o skip
  for j in $BUDGETED; do
    skip=0
    for o in "$@"; do [ "${o%%|*}" = "$j" ] && skip=1; done
    [ "$skip" -eq 1 ] || out="${out}${j}|SUCCESS|600"$'\n'
  done
  for o in "$@"; do out="${out}${o}"$'\n'; done
  printf '%s' "$out"
}

@test "the watchdog logic is extractable from the deployed manifest" {
  [ -s "$LOGIC" ]
  grep -q 'DagsterJobNeverRan' "$LOGIC"
  [ "$(printf '%s\n' "$BUDGETED" | grep -c .)" -ge 10 ]
}

@test "every budgeted job fresh and passing fires nothing" {
  stub psql 0 "$(rows)"
  run sh "$LOGIC"
  [ "$status" -eq 0 ]
  [[ "$output" == *"done — 0 alert(s) fired"* ]]
}

@test "a budgeted job with no runs at all fires DagsterJobNeverRan naming it" {
  stub psql 0 "$(rows | grep -v '^linear_backup_job|')"
  run sh "$LOGIC"
  [ "$status" -eq 0 ]
  [[ "$output" == *"ALERT DagsterJobNeverRan job=linear_backup_job"* ]]
  grep -q 'DagsterJobNeverRan' "$STUB_LOG"
}

@test "a job whose latest run FAILED fires DagsterJobFailed" {
  stub psql 0 "$(rows 'weyland_dbt_job|FAILURE|600')"
  run sh "$LOGIC"
  [[ "$output" == *"ALERT DagsterJobFailed job=weyland_dbt_job"* ]]
  [[ "$output" != *"DagsterJobStale job=weyland_dbt_job"* ]]
}

@test "a job past its budget fires DagsterJobStale" {
  stub psql 0 "$(rows 'weyland_catalog_job|SUCCESS|200000')"
  run sh "$LOGIC"
  [[ "$output" == *"ALERT DagsterJobStale job=weyland_catalog_job"* ]]
}

@test "an unbudgeted (on-demand) job is ignored, whatever its state" {
  stub psql 0 "$(rows 'weyland_datasets_music_hydrate_job|FAILURE|9999999')"
  run sh "$LOGIC"
  [[ "$output" == *"done — 0 alert(s) fired"* ]]
}

@test "an empty run list fails closed, never 0 alerts" {
  stub psql 0 ''
  run sh "$LOGIC"
  [ "$status" -ne 0 ]
  [[ "$output" == *"no runs"* ]]
  [[ "$output" != *"alert(s) fired"* ]]
}

@test "a psql failure fails the Job and still releases the istio sidecar" {
  stub psql 2 'psql: error: connection refused'
  run sh "$LOGIC"
  [ "$status" -ne 0 ]
  grep -q 'quitquitquit' "$STUB_LOG"
}
