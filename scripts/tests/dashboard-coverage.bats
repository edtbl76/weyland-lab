#!/usr/bin/env bats
# Coverage logic for scripts/check-dashboard-coverage.sh.
#
# The guard proves "no active service without a dashboard" (DoD Pillar 6). A job is covered by a UNION
# of two signals: (1) a dashboard names it (`job="X"` / `job=~"pat"`), or (2) a dashboard charts a metric
# DISTINCTIVE to it (exported by ≤ DIST_THRESHOLD jobs). These tests drive it with fixtures (UP_JOBS_FILE
# + DASH_JSON_FILE + METRIC_JOBS_FILE) so nothing touches the live cluster.

setup() {
  load helper
  SCRIPT="$REPO_ROOT/scripts/check-dashboard-coverage.sh"
  WORK="$(mktemp -d)"
  echo '{}' >"$WORK/mj.json"   # default: no metric→job map (signal (2) off unless a test sets it)
}

teardown() {
  [ -n "${WORK:-}" ] && rm -rf "$WORK"
  return 0
}

# a kubectl-style ConfigMap-list JSON whose single dashboard embeds $1 as its panel text
dash_fixture() {
  python3 - "$1" >"$WORK/dash.json" <<'PY'
import json, sys
print(json.dumps({"items": [{"data": {"d.json": sys.argv[1]}}]}))
PY
  export DASH_JSON_FILE="$WORK/dash.json"
}

up_fixture() {  # up_fixture job1 job2 ...
  printf '%s\n' "$@" >"$WORK/up.txt"
  export UP_JOBS_FILE="$WORK/up.txt"
}

mj_fixture() {  # mj_fixture '<json object metric->[jobs]>'
  printf '%s' "$1" >"$WORK/mj.json"
  export METRIC_JOBS_FILE="$WORK/mj.json"
}

@test "covered_jobs: a job named by a job=\"X\" literal is covered" {
  DASHBOARD_COVERAGE_LIB=1 source "$SCRIPT"
  echo 'trino' >"$WORK/up.txt"
  dash_fixture 'up{job="trino"}'
  run covered_jobs "$WORK/up.txt" "$WORK/dash.json" "$WORK/mj.json" 5
  [ "$status" -eq 0 ]
  [ "$output" = "trino" ]
}

@test "covered_jobs: a job=~ pattern covers the job AND its scrape-twin" {
  DASHBOARD_COVERAGE_LIB=1 source "$SCRIPT"
  printf 'minio\nminio-s3-lan\n' >"$WORK/up.txt"
  dash_fixture 'max(minio_cluster_bucket_total{job=~"minio.*"})'
  run covered_jobs "$WORK/up.txt" "$WORK/dash.json" "$WORK/mj.json" 5
  [ "$status" -eq 0 ]
  [[ "$output" == *"minio"* ]]
  [[ "$output" == *"minio-s3-lan"* ]]
}

@test "covered_jobs: a DISTINCTIVE metric covers its job even with no job= filter (signal 2)" {
  # The reason this guard is a union: the CoreDNS board scopes by \$job, never a literal job=, but it
  # charts coredns_* — a metric only coredns exports — so the coverage is real and verified.
  DASHBOARD_COVERAGE_LIB=1 source "$SCRIPT"
  echo 'coredns' >"$WORK/up.txt"
  dash_fixture 'sum(rate(coredns_dns_requests_total[5m]))'
  mj_fixture '{"coredns_dns_requests_total": ["coredns"]}'
  run covered_jobs "$WORK/up.txt" "$WORK/dash.json" "$WORK/mj.json" 5
  [ "$status" -eq 0 ]
  [ "$output" = "coredns" ]
}

@test "covered_jobs: a metric spread across MANY jobs confers NO coverage (up, process_*)" {
  # A board that only charts `up` cannot vacuously cover the estate — `up` is over the distinctiveness
  # threshold, so it is not a coverage signal for any single job.
  DASHBOARD_COVERAGE_LIB=1 source "$SCRIPT"
  echo 'weyland-guard' >"$WORK/up.txt"
  dash_fixture 'process_cpu_seconds_total'
  mj_fixture '{"process_cpu_seconds_total": ["a","b","c","d","e","f","weyland-guard"]}'
  run covered_jobs "$WORK/up.txt" "$WORK/dash.json" "$WORK/mj.json" 5
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "is_accepted: a documented exception matches; anything else does not" {
  DASHBOARD_COVERAGE_LIB=1 source "$SCRIPT"
  run is_accepted opencost
  [ "$status" -eq 0 ]
  run is_accepted loki
  [ "$status" -eq 0 ]
  run is_accepted minio
  [ "$status" -ne 0 ]
}

@test "main: an uncovered, unaccepted job is a GAP — exit 1, named" {
  up_fixture trino minio
  dash_fixture 'up{job="trino"}'
  mj_fixture '{"minio_cluster_bucket_total": ["minio"]}'   # minio's metric present but no dashboard charts it
  run bash "$SCRIPT"
  [ "$status" -eq 1 ]
  [[ "$output" == *"GAP"* ]]
  [[ "$output" == *"minio"* ]]
  [[ "$output" != *"GAP   trino"* ]]
}

@test "main: every job covered or accepted → exit 0" {
  up_fixture trino opencost
  dash_fixture 'up{job="trino"}'   # trino covered by job=, opencost ACCEPTED
  run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK"* ]]
}

@test "main: a job covered ONLY by a distinctive metric passes" {
  up_fixture coredns
  dash_fixture 'sum(rate(coredns_dns_requests_total[5m]))'
  mj_fixture '{"coredns_dns_requests_total": ["coredns"]}'
  run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK"* ]]
}

@test "main: ZERO scrape jobs fails closed — exit 2, never a clean pass" {
  : >"$WORK/up.txt"
  export UP_JOBS_FILE="$WORK/up.txt"
  dash_fixture 'up{job="trino"}'
  run bash "$SCRIPT"
  [ "$status" -eq 2 ]
  [[ "$output" == *"ZERO"* ]]
}

@test "main --list: prints a verdict for every job and exits 0 even with a gap" {
  up_fixture trino minio opencost
  dash_fixture 'up{job="trino"}'
  run bash "$SCRIPT" --list
  [ "$status" -eq 0 ]
  [[ "$output" == *"ok"*"trino"* ]]
  [[ "$output" == *"ACCEPTED"*"opencost"* ]]
  [[ "$output" == *"GAP"*"minio"* ]]
}
