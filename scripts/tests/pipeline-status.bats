#!/usr/bin/env bats
# scripts/ci/pipeline-status.sh (B200, 2026-11-18) — the TRUE status of a multi-workflow pipeline, for the `finish`
# workflow's notify steps. Inside a workflow, $CI_PIPELINE_STATUS and `when: status` only see THAT workflow: on the
# throwaway branch b200-status-test, pipeline #683 failed (workflow `bad`) while `finish` read CI_PIPELINE_STATUS=success
# and ran its success-gated step. So the status is read from Woodpecker's API (anonymous read works: weyland-lab is
# public). Fixtures are the real #683 (failed) and #684 (passed) responses, trimmed to number/status/workflows.
# PIPELINE_JSON_FILE is the test seam that replaces the HTTP call.

setup() {
  S="$BATS_TEST_DIRNAME/../ci/pipeline-status.sh"
  FX="$BATS_TEST_DIRNAME/fixtures/pipeline-status"
  export CI_WORKFLOW_NAME=finish
}

@test "a failed workflow elsewhere is failure, even though finish itself succeeded (#683)" {
  run env PIPELINE_JSON_FILE="$FX/pipeline-683.json" bash "$S"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [ "$(echo "$output" | head -1)" = "failure" ] || { echo "$output"; return 1; }
  [[ "$output" == *"bad=failure"* ]] || { echo "$output"; return 1; }
}

@test "every other workflow success or skipped is success (#684)" {
  run env PIPELINE_JSON_FILE="$FX/pipeline-684.json" bash "$S"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [ "$(echo "$output" | head -1)" = "success" ] || { echo "$output"; return 1; }
}

@test "a skipped workflow alone does not fail the pipeline (a lean run skips steps, not workflows)" {
  f="$BATS_TEST_TMPDIR/p.json"
  printf '{"number":1,"workflows":[{"name":"platform","state":"success"},{"name":"golden-path","state":"skipped"},{"name":"finish","state":"running"}]}' > "$f"
  run env PIPELINE_JSON_FILE="$f" bash "$S"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [ "$(echo "$output" | head -1)" = "success" ] || { echo "$output"; return 1; }
}

@test "the caller's own workflow is ignored, whatever its state" {
  f="$BATS_TEST_TMPDIR/p.json"
  printf '{"number":1,"workflows":[{"name":"platform","state":"success"},{"name":"finish","state":"running"}]}' > "$f"
  run env PIPELINE_JSON_FILE="$f" bash "$S"
  [ "$(echo "$output" | head -1)" = "success" ] || { echo "$output"; return 1; }
}

@test "error and killed count as failure" {
  for st in error killed; do
    f="$BATS_TEST_TMPDIR/p-$st.json"
    printf '{"number":1,"workflows":[{"name":"platform","state":"%s"},{"name":"finish","state":"running"}]}' "$st" > "$f"
    run env PIPELINE_JSON_FILE="$f" bash "$S"
    [ "$(echo "$output" | head -1)" = "failure" ] || { echo "$st: $output"; return 1; }
  done
}

@test "another workflow still running is unknown: prints failure (fail closed) and exits 2, naming it" {
  f="$BATS_TEST_TMPDIR/p.json"
  printf '{"number":1,"workflows":[{"name":"platform","state":"running"},{"name":"finish","state":"running"}]}' > "$f"
  run env PIPELINE_JSON_FILE="$f" bash "$S"
  [ "$status" -eq 2 ] || { echo "$output"; return 1; }
  [ "$(echo "$output" | head -1)" = "failure" ] || { echo "$output"; return 1; }
  [[ "$output" == *"UNKNOWN"*"platform=running"* ]] || { echo "$output"; return 1; }
}

@test "no workflows other than the caller is unknown, never success" {
  f="$BATS_TEST_TMPDIR/p.json"
  printf '{"number":1,"workflows":[{"name":"finish","state":"running"}]}' > "$f"
  run env PIPELINE_JSON_FILE="$f" bash "$S"
  [ "$status" -eq 2 ] || { echo "$output"; return 1; }
  [ "$(echo "$output" | head -1)" = "failure" ] || { echo "$output"; return 1; }
  [[ "$output" == *"UNKNOWN"*"no other workflow"* ]] || { echo "$output"; return 1; }
}

@test "an unreadable response is unknown, never success" {
  f="$BATS_TEST_TMPDIR/p.json"
  printf 'not json' > "$f"
  run env PIPELINE_JSON_FILE="$f" bash "$S"
  [ "$status" -eq 2 ] || { echo "$output"; return 1; }
  [ "$(echo "$output" | head -1)" = "failure" ] || { echo "$output"; return 1; }
  [[ "$output" == *"UNKNOWN"*"cannot read"* ]] || { echo "$output"; return 1; }
}

@test "without CI_WORKFLOW_NAME it refuses (exit 2), so it can never count itself as another workflow" {
  run env -u CI_WORKFLOW_NAME PIPELINE_JSON_FILE="$FX/pipeline-684.json" bash "$S"
  [ "$status" -eq 2 ] || { echo "$output"; return 1; }
  [ "$(echo "$output" | head -1)" = "failure" ] || { echo "$output"; return 1; }
  [[ "$output" == *"CI_WORKFLOW_NAME"* ]] || { echo "$output"; return 1; }
}
