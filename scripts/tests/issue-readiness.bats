#!/usr/bin/env bats
# B190 — the issue-readiness wrapper fails CLOSED. Linear unreachable, or no key, is exit 2 with the REASON printed —
# never READY, and never a bare non-zero that a missing script (127) would also produce. The checking decisions are
# pinned in tests/test_issue_readiness.py; this proves the real entrypoint.

load helper

setup() {
  export ISSUE_READINESS_ENV="/nonexistent/no.env"        # never read the developer's real scripts/.env
}

@test "Linear unreachable is exit 2 'linear unavailable', never READY" {
  ISSUE_READINESS_LINEAR_URL=http://127.0.0.1:9/graphql LINEAR_API_KEY=dummy \
    run bash "$REPO_ROOT/scripts/issue-readiness.sh" EMA-249 --no-comment
  [ "$status" -eq 2 ]
  [[ "$output" == *"linear unavailable"* ]]
  [[ "$output" != *"READY"* ]]
}

@test "no Linear key is exit 2 naming the missing key" {
  run env -u LINEAR_API_KEY bash "$REPO_ROOT/scripts/issue-readiness.sh" EMA-249
  [ "$status" -eq 2 ]
  [[ "$output" == *"LINEAR_API_KEY is not set"* ]]
}

@test "no issue given is a usage error, exit 2" {
  LINEAR_API_KEY=dummy run bash "$REPO_ROOT/scripts/issue-readiness.sh"
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage"* ]]
}
