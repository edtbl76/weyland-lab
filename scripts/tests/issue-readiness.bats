#!/usr/bin/env bats
# B190 — the issue-readiness wrapper fails CLOSED. A judge that cannot be reached, or a missing credential, is exit 2
# with the REASON printed — never a score, and never a bare non-zero that a missing script (127) would also produce.
# The scoring decisions themselves are pinned in tests/test_issue_readiness.py; this proves the real entrypoint.

load helper

setup() {
  WORK="$(mktemp -d)"
  export ISSUE_READINESS_ENV="$WORK/no-such.env"     # never read the developer's real scripts/.env
  cat >"$WORK/issue.json" <<'EOF'
{"identifier": "EMA-999", "uuid": "u-999", "title": "B999 — test", "description": "## Why\n\nBecause it broke.\n",
 "priority": 2, "labels": [], "project": "Weyland Lab"}
EOF
}

teardown() {
  rm -rf "$WORK"
}

@test "gateway down is exit 2 'scorer unavailable', never a score" {
  LITELLM_API_KEY=dummy LITELLM_API_BASE=http://127.0.0.1:9 \
    run bash "$REPO_ROOT/scripts/issue-readiness.sh" --issue-file "$WORK/issue.json" --no-comment
  [ "$status" -eq 2 ]
  [[ "$output" == *"scorer unavailable"* ]]
  [[ "$output" != *"/100"* ]]
}

@test "no LiteLLM key is exit 2 naming the missing key" {
  run env -u LITELLM_API_KEY bash "$REPO_ROOT/scripts/issue-readiness.sh" --issue-file "$WORK/issue.json" --no-comment
  [ "$status" -eq 2 ]
  [[ "$output" == *"LITELLM_API_KEY is not set"* ]]
}

@test "commenting with no Linear key is exit 2 'linear unavailable'" {
  run env -u LINEAR_API_KEY LITELLM_API_KEY=dummy bash "$REPO_ROOT/scripts/issue-readiness.sh" EMA-999
  [ "$status" -eq 2 ]
  [[ "$output" == *"linear unavailable"* ]]
}

@test "no issue given is a usage error, exit 2" {
  run bash "$REPO_ROOT/scripts/issue-readiness.sh"
  [ "$status" -eq 2 ]
  [[ "$output" == *"usage"* ]]
}
