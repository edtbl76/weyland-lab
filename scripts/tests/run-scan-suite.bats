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
  export SCAN_LOG_FILE="$STUB_DIR/scan.log"
  export SCAN_POLL_INTERVAL=0
}

teardown() { teardown_stubs; }

@test "a scan that completes exits 0 and prints the findings to triage" {
  stub_case kubectl 'get job' 0 'SuccessCriteriaMet Complete '
  run bash "$SUITE" 60
  [ "$status" -eq 0 ]
  [[ "$output" == *"scan complete"* ]]
  [[ "$output" == *"bandit: 0C / 1H"* ]]
}

@test "a scan that did not complete in time exits 2, never 0 — and still shows the partial logs" {
  stub_case kubectl 'get job' 0 ''        # no terminal condition yet: still running
  run bash "$SUITE" 1
  [ "$status" -eq 2 ]
  [[ "$output" == *"did not report complete"* ]]
  [[ "$output" == *"NOT a clean scan"* ]]
  [[ "$output" == *"bandit: 0C / 1H"* ]]   # the partial findings are still printed for the operator
}

@test "a unitless wait is read as seconds" {
  stub_case kubectl 'get job' 0 'SuccessCriteriaMet Complete '
  run bash "$SUITE" 900
  [[ "$output" == *"waiting up to 900s"* ]] || { echo "$output"; return 1; }
}

# 2026-10-16: the default wait was 900s while a full run took 43 minutes, and with B213's 23 image scans over 60. A
# plain `run-scan-suite.sh` therefore ALWAYS exited 2; the default must outlast a full run.
@test "with no argument the wait is long enough for a full run (5400s)" {
  stub_case kubectl 'get job' 0 'SuccessCriteriaMet Complete '
  run bash "$SUITE"
  [[ "$output" == *"waiting up to 5400s"* ]] || { echo "$output"; return 1; }
}

# 2026-10-15: the script printed `--tail=200` of a ~25,000-line log under "triage NEW critical/high below", so only the
# last two repos showed and weyland-lab's critical/high totals never reached the screen. The summary reads the WHOLE log.
@test "a repo early in a long log still has its critical/high totals shown, with its archive path" {
  stub_case kubectl 'get job' 0 'SuccessCriteriaMet Complete '
  { echo "======================= scan-suite: edtbl76/weyland-lab ======================="
    echo "  = trivy: 17C / 68H / 463M / 1507L (total 2055)"
    echo "  = ruff: 0C / 0H / 55M / 142L (total 197)"
    echo "  = archive: 15 file(s) → s3://scan-reports/2026-10-15T04-17-42Z/ (90d ILM)"
    for i in $(seq 1 400); do echo "noise line $i"; done
    echo "======================= scan-suite: edtbl76/grkit ======================="
    echo "  = bandit: 0C / 0H / 1M / 53L (total 54)"; } >"$STUB_DIR/biglog"
  printf 'logs|0|%s\n' "$STUB_DIR/biglog" >"$STUB_DIR/.kubectl.cases.new"
  grep -v '^logs|' "$STUB_DIR/.kubectl.cases" >>"$STUB_DIR/.kubectl.cases.new"; mv "$STUB_DIR/.kubectl.cases.new" "$STUB_DIR/.kubectl.cases"
  run bash "$SUITE" 60
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"edtbl76/weyland-lab  trivy: 17C / 68H"* ]]
  [[ "$output" == *"edtbl76/weyland-lab  archive: 15 file(s)"* ]]
  [[ "$output" != *"ruff:"* ]]          # no critical/high: not listed
  [[ "$output" != *"grkit  bandit"* ]]
  [[ "$output" == *"(3 tool result(s) read)"* ]]
  grep -q -- '--tail=-1' "$STUB_LOG"
}

@test "a completed job with an empty log is NOT a clean scan (exit 2)" {
  stub_case kubectl 'get job' 0 'SuccessCriteriaMet Complete '
  : >"$STUB_DIR/empty"
  printf 'logs|0|%s\n' "$STUB_DIR/empty" >"$STUB_DIR/.kubectl.cases.new"
  grep -v '^logs|' "$STUB_DIR/.kubectl.cases" >>"$STUB_DIR/.kubectl.cases.new"; mv "$STUB_DIR/.kubectl.cases.new" "$STUB_DIR/.kubectl.cases"
  run bash "$SUITE" 60
  [ "$status" -eq 2 ]
  [[ "$output" == *"could not read any log"* ]]
}

@test "a completed job whose log has no tool results is NOT a clean scan (exit 2)" {
  stub_case kubectl 'get job' 0 'SuccessCriteriaMet Complete '
  echo "Error from server: something went wrong" >"$STUB_DIR/junk"
  printf 'logs|0|%s\n' "$STUB_DIR/junk" >"$STUB_DIR/.kubectl.cases.new"
  grep -v '^logs|' "$STUB_DIR/.kubectl.cases" >>"$STUB_DIR/.kubectl.cases.new"; mv "$STUB_DIR/.kubectl.cases.new" "$STUB_DIR/.kubectl.cases"
  run bash "$SUITE" 60
  [ "$status" -eq 2 ]
  [[ "$output" == *"no '= <tool>:"* ]]
}

# 2026-10-16: scan.py exits 3 on a scan defect (a crashed tool, an unscanned image) and the CronJob's podFailurePolicy
# fails the Job. `kubectl wait --for=condition=complete` never returns for a FAILED Job, so the script used to sit out
# its whole 90-minute wait. It now polls for either terminal condition.
@test "a FAILED job is NOT a clean scan (exit 2), names the defect, and does not wait out the timeout" {
  stub_case kubectl 'get job' 0 'FailureTarget Failed '
  printf '%s\n' '======================= scan-suite: edtbl76/weyland-lab =======================' \
    '  = bandit: 0C / 1H / 74M / 2068L (total 2143)' \
    '  !! trivy-images: 1 image(s) could not be scanned [registry.weyland.lab/a:git-1], 0 with no pinned tag []' \
    '  !! SCAN DEFECT: trivy-images could not scan registry.weyland.lab/a:git-1' >"$STUB_DIR/flog"
  printf 'logs|0|%s\n' "$STUB_DIR/flog" >"$STUB_DIR/.kubectl.cases.new"
  grep -v '^logs|' "$STUB_DIR/.kubectl.cases" >>"$STUB_DIR/.kubectl.cases.new"; mv "$STUB_DIR/.kubectl.cases.new" "$STUB_DIR/.kubectl.cases"
  SECONDS=0
  run bash "$SUITE" 3600
  [ "$status" -eq 2 ] || { echo "$output"; return 1; }
  [[ "$output" == *"FAILED"* && "$output" == *"SCAN DEFECT: trivy-images could not scan registry.weyland.lab/a:git-1"* ]] || { echo "$output"; return 1; }
  [ "$SECONDS" -lt 30 ]
}
