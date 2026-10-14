#!/usr/bin/env bats
#
# run-scan-suite.sh — the DoD Pillar 7 gate MUST fail closed when the scan did not finish.
#
# Found 2026-10-14 during the B207 DoD pass: the job outlived its wait (trivy still running), the script printed
# "did not report complete … (failed or still running)", and exited 0. A gate that cannot say the scan finished is
# the absence-as-success class (project.md), here inside the gate built to catch it. Asserts on the REASON as well
# as the status, so a missing script (exit 127) cannot pass for the right failure.

load helper

setup() {
  setup_stubs
  SUITE="$REPO_ROOT/scripts/run-scan-suite.sh"
  stub_dispatch kubectl
  stub_case kubectl 'delete job' 0 ''
  stub_case kubectl 'create job' 0 'job.batch/scan-suite-adhoc created'
  stub_case kubectl 'logs' 0 '  = bandit: 0C / 1H / 74M / 2068L (total 2143)'
}

teardown() { teardown_stubs; }

@test "a scan that completes exits 0 and prints the findings to triage" {
  stub_case kubectl 'wait' 0 'job.batch/scan-suite-adhoc condition met'
  run bash "$SUITE" 60
  [ "$status" -eq 0 ]
  [[ "$output" == *"scan complete"* ]]
  [[ "$output" == *"= bandit:"* ]]
}

@test "a scan that did not complete in time exits 2, never 0 — and still shows the partial logs" {
  stub_case kubectl 'wait' 1 'error: timed out waiting for the condition on jobs/scan-suite-adhoc'
  run bash "$SUITE" 60
  [ "$status" -eq 2 ]
  [[ "$output" == *"did not report complete"* ]]
  [[ "$output" == *"NOT a clean scan"* ]]
  [[ "$output" == *"= bandit:"* ]]   # the partial findings are still printed for the operator
}

@test "a unitless wait is normalized to seconds (kubectl wait requires a unit)" {
  stub_case kubectl 'wait' 0 'condition met'
  run bash "$SUITE" 900
  grep -q -- '--timeout=900s' "$STUB_LOG"
}
