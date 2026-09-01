#!/usr/bin/env bats
# Coverage logic for scripts/check-alert-coverage.sh.
#
# A job is protected when a DOWN/absent alert covers it: a BLANKET rule (up/absent, no job filter — the
# kube-prometheus-stack TargetDown) covers every job at once, or a JOB-SCOPED down alert names it. The
# guard's value is failing LOUD if the blanket net is ever removed and a job is left unprotected. Tests
# drive it with fixtures (UP_RAW_FILE + RULES_JSON_FILE / a newline up-file for the pure function).

setup() {
  load helper
  SCRIPT="$REPO_ROOT/scripts/check-alert-coverage.sh"
  WORK="$(mktemp -d)"
}

teardown() {
  [ -n "${WORK:-}" ] && rm -rf "$WORK"
  return 0
}

# a PrometheusRule-list JSON wrapping $1 (a JSON array of rule objects) as one group
rules_fixture() {
  python3 - "$1" >"$WORK/rules.json" <<'PY'
import json, sys
print(json.dumps({"items": [{"spec": {"groups": [{"name": "g", "rules": json.loads(sys.argv[1])}]}}]}))
PY
  export RULES_JSON_FILE="$WORK/rules.json"
}

up_raw() {  # up_raw job1 job2 ...  -> raw /api/v1/query body via UP_RAW_FILE
  python3 - "$@" >"$WORK/up_raw.json" <<'PY'
import json, sys
print(json.dumps({"data": {"result": [{"metric": {"job": j}} for j in sys.argv[1:]]}}))
PY
  export UP_RAW_FILE="$WORK/up_raw.json"
}

# ---- covered_jobs (pure): newline up-file + PrometheusRules JSON ----

@test "covered_jobs: a blanket down alert (no job=) covers EVERY job" {
  ALERT_COVERAGE_LIB=1 source "$SCRIPT"
  printf 'minio\nweyland-guard\n' >"$WORK/up.txt"
  rules_fixture '[{"alert":"TargetDown","expr":"100 * (count(up == 0) BY (job) / count(up) BY (job)) > 10"}]'
  run covered_jobs "$WORK/up.txt" "$WORK/rules.json"
  [ "$status" -eq 0 ]
  [[ "$output" == *"minio"* ]]
  [[ "$output" == *"weyland-guard"* ]]
}

@test "covered_jobs: a job-scoped up==0 alert covers ONLY that job" {
  ALERT_COVERAGE_LIB=1 source "$SCRIPT"
  printf 'kubelet\nminio\n' >"$WORK/up.txt"
  rules_fixture '[{"alert":"KubeletDown","expr":"up{job=\"kubelet\"} == 0"}]'
  run covered_jobs "$WORK/up.txt" "$WORK/rules.json"
  [ "$status" -eq 0 ]
  [ "$output" = "kubelet" ]
}

@test "covered_jobs: absent(up{job=X}) covers X" {
  ALERT_COVERAGE_LIB=1 source "$SCRIPT"
  printf 'tempo\nminio\n' >"$WORK/up.txt"
  rules_fixture '[{"alert":"TempoDown","expr":"absent(up{job=\"tempo\"})"}]'
  run covered_jobs "$WORK/up.txt" "$WORK/rules.json"
  [ "$status" -eq 0 ]
  [ "$output" = "tempo" ]
}

@test "covered_jobs: a NON-down alert referencing the job confers no down-coverage" {
  ALERT_COVERAGE_LIB=1 source "$SCRIPT"
  echo 'trino' >"$WORK/up.txt"
  rules_fixture '[{"alert":"TrinoSlow","expr":"histogram_quantile(0.95, rate(x_bucket{job=\"trino\"}[5m])) > 1"}]'
  run covered_jobs "$WORK/up.txt" "$WORK/rules.json"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

@test "covered_jobs: a recording rule (no alert:) protects nothing" {
  ALERT_COVERAGE_LIB=1 source "$SCRIPT"
  echo 'x' >"$WORK/up.txt"
  rules_fixture '[{"record":"job:up:down","expr":"up{job=\"x\"} == 0"}]'
  run covered_jobs "$WORK/up.txt" "$WORK/rules.json"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}

# ---- main (whole guard) ----

@test "main: the blanket net protects every job → exit 0" {
  up_raw minio weyland-guard trino
  rules_fixture '[{"alert":"TargetDown","expr":"count(up == 0) BY (job) > 0"}]'
  run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"OK"* ]]
}

@test "main: net removed leaves a job with no dedicated alert a GAP; a scoped job stays ok" {
  up_raw kubelet minio
  rules_fixture '[{"alert":"KubeletDown","expr":"up{job=\"kubelet\"} == 0"}]'
  run bash "$SCRIPT"
  [ "$status" -eq 1 ]
  [[ "$output" == *"GAP"* ]]
  [[ "$output" == *"minio"* ]]
  [[ "$output" != *"GAP   kubelet"* ]]
}

@test "main: ZERO scrape jobs fails closed — exit 2" {
  up_raw
  rules_fixture '[]'
  run bash "$SCRIPT"
  [ "$status" -eq 2 ]
  [[ "$output" == *"ZERO"* ]]
}

@test "main --list: a verdict per job, exit 0 even with a gap" {
  up_raw kubelet minio
  rules_fixture '[{"alert":"KubeletDown","expr":"up{job=\"kubelet\"} == 0"}]'
  run bash "$SCRIPT" --list
  [ "$status" -eq 0 ]
  [[ "$output" == *"ok"*"kubelet"* ]]
  [[ "$output" == *"GAP"*"minio"* ]]
}

@test "the CronJob embeds a byte-identical copy of the guard (no drift)" {
  MANIFEST="$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s/monitoring/alert-coverage.yaml"
  run python3 -c "
import yaml, sys
docs=list(yaml.safe_load_all(open('$MANIFEST')))
cm=[d for d in docs if d and d.get('kind')=='ConfigMap' and d['metadata']['name']=='alert-coverage-logic'][0]
emb=cm['data']['check-alert-coverage.sh']
repo=open('$REPO_ROOT/scripts/check-alert-coverage.sh').read()
sys.exit(0 if emb==repo else 1)
"
  [ "$status" -eq 0 ]
}
