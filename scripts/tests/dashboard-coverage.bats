#!/usr/bin/env bats
# Coverage logic for scripts/check-dashboard-coverage.sh.
#
# A job is covered by a UNION of two signals: (1) a dashboard names it (`job="X"` / `job=~"pat"`), or
# (2) a dashboard charts a metric DISTINCTIVE to it (exported by ≤ DIST_THRESHOLD jobs). The covered_jobs
# unit tests drive that pure function directly (newline up-file + parsed metric→job map). The main tests
# drive the whole guard through the SAME parser the CronJob uses: RAW /api/v1/query bodies via
# UP_RAW_FILE / METRIC_JOBS_RAW_FILE, plus a ConfigMap-list body via DASH_JSON_FILE. Nothing touches live.

setup() {
  load helper
  SCRIPT="$REPO_ROOT/scripts/check-dashboard-coverage.sh"
  WORK="$(mktemp -d)"
  echo '{}' >"$WORK/mj.json"   # default parsed metric→job map (empty ⇒ signal (2) off unless a test sets it)
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

# raw /api/v1/query body for `count by (job) (up)`
up_raw() {  # up_raw job1 job2 ...
  python3 - "$@" >"$WORK/up_raw.json" <<'PY'
import json, sys
print(json.dumps({"data": {"result": [{"metric": {"job": j}} for j in sys.argv[1:]]}}))
PY
  export UP_RAW_FILE="$WORK/up_raw.json"
}

# raw /api/v1/query body for the metric→job map, built from a parsed {metric:[jobs]} object
mj_raw() {  # mj_raw '{"m":["j1","j2"],...}'
  python3 - "$1" >"$WORK/mj_raw.json" <<'PY'
import json, sys
mj = json.loads(sys.argv[1])
res = [{"metric": {"__name__": m, "job": j}} for m, js in mj.items() for j in js]
print(json.dumps({"data": {"result": res}}))
PY
  export METRIC_JOBS_RAW_FILE="$WORK/mj_raw.json"
}

# ---- covered_jobs (the pure function): newline up-file + parsed metric→job map ----

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
  DASHBOARD_COVERAGE_LIB=1 source "$SCRIPT"
  echo 'coredns' >"$WORK/up.txt"
  dash_fixture 'sum(rate(coredns_dns_requests_total[5m]))'
  echo '{"coredns_dns_requests_total": ["coredns"]}' >"$WORK/mj.json"
  run covered_jobs "$WORK/up.txt" "$WORK/dash.json" "$WORK/mj.json" 5
  [ "$status" -eq 0 ]
  [ "$output" = "coredns" ]
}

@test "covered_jobs: a metric spread across MANY jobs confers NO coverage (up, process_*)" {
  DASHBOARD_COVERAGE_LIB=1 source "$SCRIPT"
  echo 'weyland-guard' >"$WORK/up.txt"
  dash_fixture 'process_cpu_seconds_total'
  echo '{"process_cpu_seconds_total": ["a","b","c","d","e","f","weyland-guard"]}' >"$WORK/mj.json"
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

# ---- main (the whole guard): raw Prometheus bodies via the shared parser ----

@test "main: an uncovered, unaccepted job is a GAP — exit 1, named" {
  up_raw trino minio
  dash_fixture 'up{job="trino"}'
  mj_raw '{"minio_cluster_bucket_total": ["minio"]}'   # minio's metric exists but no dashboard charts it
  run bash "$SCRIPT"
  [ "$status" -eq 1 ]
  [[ "$output" == *"GAP"* ]]
  [[ "$output" == *"minio"* ]]
  [[ "$output" != *"GAP   trino"* ]]
}

@test "main: every job covered or accepted → exit 0" {
  up_raw trino opencost
  dash_fixture 'up{job="trino"}'
  mj_raw '{}'
  run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK"* ]]
}

@test "main: a job covered ONLY by a distinctive metric passes" {
  up_raw coredns
  dash_fixture 'sum(rate(coredns_dns_requests_total[5m]))'
  mj_raw '{"coredns_dns_requests_total": ["coredns"]}'
  run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK"* ]]
}

@test "main: ZERO scrape jobs fails closed — exit 2, never a clean pass" {
  up_raw                       # no jobs in the result
  dash_fixture 'up{job="trino"}'
  mj_raw '{}'
  run bash "$SCRIPT"
  [ "$status" -eq 2 ]
  [[ "$output" == *"ZERO"* ]]
}

@test "main --list: prints a verdict for every job and exits 0 even with a gap" {
  up_raw trino minio opencost
  dash_fixture 'up{job="trino"}'
  mj_raw '{}'
  run bash "$SCRIPT" --list
  [ "$status" -eq 0 ]
  [[ "$output" == *"ok"*"trino"* ]]
  [[ "$output" == *"ACCEPTED"*"opencost"* ]]
  [[ "$output" == *"GAP"*"minio"* ]]
}

@test "the CronJob embeds a byte-identical copy of the guard (no drift)" {
  # Two copies of a guard drift silently on BOTH sides: the cluster runs logic nothing tests while the
  # suite stays green (B148's lesson). The script inside dashboard-coverage.yaml's ConfigMap must equal
  # scripts/check-dashboard-coverage.sh exactly. Regenerate the ConfigMap body after editing the guard —
  # the manifest is built by `sed 's/^/    /' scripts/check-dashboard-coverage.sh` under the data key.
  MANIFEST="$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s/monitoring/dashboard-coverage.yaml"
  run python3 -c "
import yaml, sys
docs=list(yaml.safe_load_all(open('$MANIFEST')))
cm=[d for d in docs if d and d.get('kind')=='ConfigMap' and d['metadata']['name']=='dashboard-coverage-logic'][0]
emb=cm['data']['check-dashboard-coverage.sh']
repo=open('$REPO_ROOT/scripts/check-dashboard-coverage.sh').read()
sys.exit(0 if emb==repo else 1)
"
  [ "$status" -eq 0 ]
}
