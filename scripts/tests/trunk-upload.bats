#!/usr/bin/env bats
#
# trunk-upload.sh (B189) — uploads every JUnit report under a root to Trunk Flaky Tests, one variant per
# subdirectory, and decides from the CLI's PRINTED output whether each upload landed.
#
# The stubbed CLI outputs below are copied from the real trunk-analytics-cli 0.16.1, observed 2026-11-06
# against the weyland org (variant b189-probe), not invented:
#   - landed, tests green:  "Upload: https://app.trunk.io/..." + "Test Report", exit 0
#   - landed, tests red:    the same two lines, "using exit code: 1", exit 1  (the UPLOAD worked)
#   - bad token:            "Error Encountered" + "Unathorized access" (sic), exit 70
#   - no files:             "Error Encountered" + "No test output files found", exit 70
#   - no CA bundle:         hangs ("taking longer than expected") — killed by timeout, exit 124
#   - an earlier no-CA run exited 0 after "unexpected error": the exit code alone is not the verdict.

load helper

setup() {
  setup_stubs
  UP="$REPO_ROOT/scripts/ci/trunk-upload.sh"
  JR="$(mktemp -d)"
  export TRUNK_API_TOKEN="test-token-value"
  export TRUNK_COLLECTION_ID="ZuFEh5e5"
  export TRUNK_CLI="$STUB_DIR/trunk-analytics-cli"
  export TRUNK_UPLOAD_TIMEOUT=30
}

teardown() {
  teardown_stubs
  [ -n "${JR:-}" ] && [ -d "$JR" ] && rm -rf "$JR"
  return 0
}

report() {   # report <variant> — one JUnit file under $JR/<variant>/
  mkdir -p "$JR/$1"
  printf '<testsuites><testsuite name="x" tests="1"><testcase classname="x" name="y"/></testsuite></testsuites>\n' > "$JR/$1/report.xml"
}

LANDED_GREEN='Upload: https://app.trunk.io/weyland/flaky-tests/collections/ZuFEh5e5/uploads/abc
Test Report
   Total: 1   Pass: 1   Fail: 0   Quarantined: 0   Pass Ratio: 100.0%
No test failures found!'

LANDED_RED='Upload: https://app.trunk.io/weyland/flaky-tests/collections/ZuFEh5e5/uploads/def
Test Report
   Total: 1   Pass: 0   Fail: 1   Quarantined: 0   Pass Ratio: 0.0%
Some test failures were not quarantined, using exit code: 1'

@test "uploads each subdirectory as its own variant and reports OK" {
  report shell-tests
  report golden-path
  stub trunk-analytics-cli 0 "$LANDED_GREEN"
  run bash "$UP" "$JR"
  [ "$status" -eq 0 ]
  called_with trunk-analytics-cli "--variant shell-tests"
  called_with trunk-analytics-cli "--variant golden-path"
  called_with trunk-analytics-cli "--allow-empty-test-results=false"
  called_with trunk-analytics-cli "--test-collection-id ZuFEh5e5"
  [[ "$output" == *"OK — 2 variant(s) uploaded"* ]]
}

@test "exit 1 from the CLI after a landed upload is failing TESTS, not a failed upload" {
  report shell-tests
  stub trunk-analytics-cli 1 "$LANDED_RED"
  run bash "$UP" "$JR"
  [ "$status" -eq 0 ]
  [[ "$output" == *"shell-tests: uploaded (tests failed"* ]]
}

@test "a bad token (Error Encountered, exit 70) fails the upload and names the variant" {
  report shell-tests
  stub trunk-analytics-cli 70 'Error Encountered
There was an unexpected error that occurred while uploading test results
Unathorized access, your Trunk organization URL slug or token may be incorrect'
  run bash "$UP" "$JR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"UPLOAD FAILED: shell-tests"* ]]
}

@test "exit 0 WITHOUT the Upload line is a failed upload (the CLI fails open)" {
  report shell-tests
  stub trunk-analytics-cli 0 'Error Encountered
There was an unexpected error that occurred while uploading test results'
  run bash "$UP" "$JR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"UPLOAD FAILED: shell-tests"* ]]
}

@test "exit 0 with the Upload line but no Test Report is a failed upload" {
  report shell-tests
  stub trunk-analytics-cli 0 'Upload: https://app.trunk.io/weyland/flaky-tests/collections/ZuFEh5e5/uploads/abc'
  run bash "$UP" "$JR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"UPLOAD FAILED: shell-tests"* ]]
}

@test "a hung upload is killed by the timeout and fails" {
  report shell-tests
  printf '#!/usr/bin/env bash\necho "taking longer than expected"\nsleep 30\n' > "$STUB_DIR/trunk-analytics-cli"
  chmod +x "$STUB_DIR/trunk-analytics-cli"
  export TRUNK_UPLOAD_TIMEOUT=1
  run bash "$UP" "$JR"
  [ "$status" -eq 1 ]
  [[ "$output" == *"UPLOAD FAILED: shell-tests"* ]]
  [[ "$output" == *"timed out"* ]]
}

@test "one failed variant does not stop the others from uploading" {
  report alpha
  report beta
  stub_dispatch trunk-analytics-cli
  stub_case trunk-analytics-cli '--variant alpha' 70 'Error Encountered'
  stub_case trunk-analytics-cli '--variant beta' 0 "$LANDED_GREEN"
  run bash "$UP" "$JR"
  [ "$status" -eq 1 ]
  called_with trunk-analytics-cli "--variant beta"
  [[ "$output" == *"UPLOAD FAILED: alpha"* ]]
  [[ "$output" == *"beta: uploaded"* ]]
}

@test "the token never appears in the output" {
  report shell-tests
  stub trunk-analytics-cli 70 "Error Encountered
token was test-token-value"
  run bash "$UP" "$JR"
  [[ "$output" != *"test-token-value"* ]]
  [[ "$output" == *"<redacted>"* ]]
}

@test "no token is exit 2 before any upload" {
  report shell-tests
  stub trunk-analytics-cli 0 "$LANDED_GREEN"
  unset TRUNK_API_TOKEN
  run bash "$UP" "$JR"
  [ "$status" -eq 2 ]
  [[ "$output" == *"TRUNK_API_TOKEN is not set"* ]]
  never_called trunk-analytics-cli
}

@test "no collection id is exit 2 before any upload" {
  report shell-tests
  stub trunk-analytics-cli 0 "$LANDED_GREEN"
  unset TRUNK_COLLECTION_ID
  run bash "$UP" "$JR"
  [ "$status" -eq 2 ]
  [[ "$output" == *"TRUNK_COLLECTION_ID is not set"* ]]
  never_called trunk-analytics-cli
}

@test "a root with no JUnit files is exit 2, never a silent pass" {
  mkdir -p "$JR/empty-lane"
  stub trunk-analytics-cli 0 "$LANDED_GREEN"
  run bash "$UP" "$JR"
  [ "$status" -eq 2 ]
  [[ "$output" == *"no JUnit reports under"* ]]
  never_called trunk-analytics-cli
}

@test "a missing root is exit 2" {
  stub trunk-analytics-cli 0 "$LANDED_GREEN"
  run bash "$UP" "$JR/does-not-exist"
  [ "$status" -eq 2 ]
  [[ "$output" == *"is not a directory"* ]]
}

@test "a variant directory with no XML is skipped and named, the others still upload" {
  report shell-tests
  mkdir -p "$JR/no-xml-here"
  stub trunk-analytics-cli 0 "$LANDED_GREEN"
  run bash "$UP" "$JR"
  [ "$status" -eq 0 ]
  not_called_with trunk-analytics-cli "--variant no-xml-here"
  [[ "$output" == *"no-xml-here: no JUnit files, skipped"* ]]
}

@test "commit and branch come from Woodpecker's CI variables when set" {
  report shell-tests
  stub trunk-analytics-cli 0 "$LANDED_GREEN"
  export CI_COMMIT_SHA=0123456789abcdef0123456789abcdef01234567
  export CI_COMMIT_BRANCH=main
  run bash "$UP" "$JR"
  [ "$status" -eq 0 ]
  called_with trunk-analytics-cli "--repo-head-sha 0123456789abcdef0123456789abcdef01234567"
  called_with trunk-analytics-cli "--repo-head-branch main"
}
