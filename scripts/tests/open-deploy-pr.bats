#!/usr/bin/env bats
# HTTP status handling in scripts/ci/open-deploy-pr.sh.
#
# THE DEFECT UNDER TEST: the step ended with `curl -sf … || { echo "…may already be open…"; exit 0; }`
# — one handler for every non-2xx. A 422 (a PR for this head is already open) and a 500 became
# indistinguishable, and BOTH left the pipeline green. That is constraint C9: the pipeline can report
# success having opened no PR.

setup() {
  load helper
  setup_stubs
  SCRIPT="$REPO_ROOT/scripts/ci/open-deploy-pr.sh"

  WORK="$(mktemp -d)"
  # A manifest path that does not exist on purpose: the script warns and skips rather than trying to
  # sed -i a file inside the read-only mount.
  printf 'scan-suite\tgit-9a4996c6\tk8s/does-not-exist/scan-suite.yaml\n' >"$WORK/bumps"

  export BUMPS="$WORK/bumps"
  export GITHUB_TOKEN="test-token-not-a-real-credential"

  stub git 0 ''
}

teardown() {
  teardown_stubs
  [ -n "${WORK:-}" ] && rm -rf "$WORK"
  return 0
}

@test "FR3.1 a 201 is the success path" {
  stub curl 0 '{"html_url":"https://github.com/edtbl76/weyland-lab/pull/14"}
201'
  run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"pull/14"* ]]
}

@test "FR3.1 a 422 is tolerated when the PR really is already open" {
  # Duplicate-head 422 on the POST, then a non-empty list on the verifying GET.
  stub_dispatch curl
  stub_case curl '-X POST' 0 '{"message":"Validation Failed"}
422'
  stub_case curl 'pulls?head=' 0 '[{"number":13,"html_url":"https://github.com/edtbl76/weyland-lab/pull/13"}]
200'
  run bash "$SCRIPT"
  [ "$status" -eq 0 ]
}

@test "FR3.1 a 500 fails the step" {
  # The whole point: this used to exit 0 with the same message as the 422 case.
  stub curl 0 '{"message":"Server Error"}
500'
  run bash "$SCRIPT"
  [ "$status" -ne 0 ]
  [[ "$output" == *"500"* ]]
}

@test "FR3.2 exits non-zero when no PR exists after the step runs" {
  # A 422 whose verifying GET comes back empty. The duplicate excuse was wrong — there is no PR, and
  # a green pipeline here is the exact false signal this work exists to remove.
  stub_dispatch curl
  stub_case curl '-X POST' 0 '{"message":"Validation Failed"}
422'
  stub_case curl 'pulls?head=' 0 '[]
200'
  run bash "$SCRIPT"
  [ "$status" -ne 0 ]
}

@test "FR3.3 the duplicate-tolerant branch still exists" {
  # Guards against "fixing" this by deleting the fallback: a re-run legitimately hits a duplicate.
  # Only the conflation of that case with real failure was the defect.
  run grep -c '422' "$SCRIPT"
  [ "$status" -eq 0 ]
  [ "$output" -ge 1 ]
}
