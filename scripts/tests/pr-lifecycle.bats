#!/usr/bin/env bats
# B131 (resolution half) — check-pr-lifecycle.sh decision logic.
#
# The script's whole job is deciding what to do with what `gh` reports, so `gh` is stubbed (stub_dispatch:
# one binary, many hats — `pr list`, `api compare`, `pr comment`, `pr close`) and every assertion is on the
# DECISION reached, never the canned JSON. The safety assertion the suite exists to hold: --apply NEVER merges,
# and it NEVER acts on a PR it could not classify (fail closed). A stray real merge/close would touch live PRs,
# so no test may let `gh` run for real.

setup() {
  load helper
  setup_stubs
  GUARD="$REPO_ROOT/scripts/check-pr-lifecycle.sh"
}

teardown() { teardown_stubs; }

# A mixed, realistic open-PR set. createdAt is ISO-8601 (lexicographic == chronological), so the superseded
# pair (#20 older, #21 newer, same package key) orders deterministically.
_pr_list_json() {
  cat <<'JSON'
[
 {"number":10,"title":"Bump quic-go 0.59.0->0.59.1","headRefName":"dependabot/go_modules/svc-a/quic-go-aaaaaaaa","createdAt":"2026-09-01T00:00:00Z","isDraft":false,"statusCheckRollup":[{"conclusion":"SUCCESS"}]},
 {"number":11,"title":"Bump aiohttp (stale)","headRefName":"dependabot/pip/svc-b/aiohttp-bbbbbbbb","createdAt":"2026-09-02T00:00:00Z","isDraft":false,"statusCheckRollup":[{"conclusion":"SUCCESS"}]},
 {"number":12,"title":"Bump left-pad (ci red)","headRefName":"dependabot/npm_and_yarn/svc-c/left-pad-cccccccc","createdAt":"2026-09-03T00:00:00Z","isDraft":false,"statusCheckRollup":[{"conclusion":"FAILURE"}]},
 {"number":13,"title":"human feature work","headRefName":"feature/my-thing","createdAt":"2026-09-04T00:00:00Z","isDraft":false,"statusCheckRollup":[{"conclusion":"SUCCESS"}]},
 {"number":20,"title":"Bump img 1.0->1.1 (older)","headRefName":"dependabot/docker/svc-d/img-dddddddd","createdAt":"2026-09-05T00:00:00Z","isDraft":false,"statusCheckRollup":[{"conclusion":"SUCCESS"}]},
 {"number":21,"title":"Bump img 1.0->1.2 (newer)","headRefName":"dependabot/docker/svc-d/img-eeeeeeee","createdAt":"2026-09-06T00:00:00Z","isDraft":false,"statusCheckRollup":[{"conclusion":"SUCCESS"}]}
]
JSON
}

# Wire the gh stub for the mixed set: #10 current (ahead), #11 stale (diverged); #12 current (ahead);
# #20/#21 current (identical) so their verdict is driven purely by supersede logic.
_wire_mixed() {
  stub_dispatch gh
  stub_case gh 'pr list' 0 "$(_pr_list_json)"
  stub_case gh 'compare/main...dependabot/go_modules/svc-a/quic-go-aaaaaaaa'    0 'ahead'
  stub_case gh 'compare/main...dependabot/pip/svc-b/aiohttp-bbbbbbbb'           0 'diverged'
  stub_case gh 'compare/main...dependabot/npm_and_yarn/svc-c/left-pad-cccccccc' 0 'ahead'
  stub_case gh 'compare/main...dependabot/docker/svc-d/img-dddddddd'            0 'identical'
  stub_case gh 'compare/main...dependabot/docker/svc-d/img-eeeeeeee'            0 'identical'
  stub_case gh 'issues' 0 ''
  stub_case gh 'pulls'  0 ''
}

@test "the guard exists" {
  [ -f "$GUARD" ]
}

@test "advisory: classifies each managed PR and prints the summary marker, exit 0" {
  _wire_mixed
  run bash "$GUARD"
  [ "$status" -eq 0 ]
  # #11 diverged -> STALE; #10 ahead+green -> MERGEABLE; #12 ci red -> NEEDS-HUMAN; #20 older -> SUPERSEDED.
  echo "$output" | grep -q '#11 \[STALE\]'
  echo "$output" | grep -q '#10 \[MERGEABLE\]'
  echo "$output" | grep -q '#12 \[NEEDS-HUMAN\]'
  echo "$output" | grep -q '#20 \[SUPERSEDED\]'
  echo "$output" | grep -q '#21 \[MERGEABLE\]'
  # summary line: 5 managed open (13 is a human feature branch, excluded).
  echo "$output" | grep -qE 'pr-lifecycle: 5 open \(1 stale, 1 superseded, 2 mergeable, 1 needs-human\)'
}

@test "advisory: a non-managed (human) branch is ignored" {
  _wire_mixed
  run bash "$GUARD"
  [ "$status" -eq 0 ]
  not_called_with gh 'compare/main...feature/my-thing'
  ! echo "$output" | grep -q '#13'
}

@test "advisory NEVER mutates — no comment, no close, no merge" {
  _wire_mixed
  run bash "$GUARD"
  [ "$status" -eq 0 ]
  not_called_with gh '-X POST'
  not_called_with gh '-X PATCH'
  not_called_with gh 'merge'
}

@test "--apply: recreates STALE and closes SUPERSEDED, but NEVER merges" {
  _wire_mixed
  run bash "$GUARD" --apply
  [ "$status" -eq 0 ]
  # STALE #11 gets a recreate comment (REST issue-comment); SUPERSEDED #20 is closed (REST PATCH state=closed).
  called_with gh 'issues/11/comments'
  called_with gh '@dependabot recreate'
  called_with gh 'pulls/20'
  # the CRITICAL safety guarantee — never a merge, by any route.
  not_called_with gh 'merge'
  # MERGEABLE #10 is left for a human — not touched.
  not_called_with gh 'issues/10/comments'
  not_called_with gh 'pulls/10'
}

@test "fail closed: gh pr list transport/auth failure -> exit 2, not a clean sweep" {
  stub_dispatch gh
  stub_case gh 'pr list' 1 'HTTP 401: Bad credentials'
  run bash "$GUARD"
  [ "$status" -eq 2 ]
  echo "$output" | grep -q 'could not list PRs'
}

@test "fail closed: an unresolvable compare is exit 2, never treated as current" {
  stub_dispatch gh
  stub_case gh 'pr list' 0 '[{"number":11,"title":"x","headRefName":"dependabot/pip/svc-b/aiohttp-bbbbbbbb","createdAt":"2026-09-02T00:00:00Z","isDraft":false,"statusCheckRollup":[{"conclusion":"SUCCESS"}]}]'
  # compare unmatched -> stub_dispatch exits 0 with EMPTY output -> compare_status must read that as ERROR.
  run bash "$GUARD"
  [ "$status" -eq 2 ]
  echo "$output" | grep -q 'could not compare'
}

@test "no open managed PRs -> clean summary, exit 0" {
  stub_dispatch gh
  stub_case gh 'pr list' 0 '[{"number":13,"title":"human","headRefName":"feature/x","createdAt":"2026-09-04T00:00:00Z","isDraft":false,"statusCheckRollup":[]}]'
  run bash "$GUARD"
  [ "$status" -eq 0 ]
  echo "$output" | grep -qE 'pr-lifecycle: 0 open \(0 stale, 0 superseded, 0 mergeable, 0 needs-human\)'
}

@test "ci/image-bump: survivor is MERGEABLE (ship loop), older is SUPERSEDED, and compare is NOT called" {
  stub_dispatch gh
  stub_case gh 'pr list' 0 '[
    {"number":40,"title":"ci: image bump (old)","headRefName":"ci/image-bump-git-aaaa1111","createdAt":"2026-09-01T00:00:00Z","isDraft":false,"statusCheckRollup":[{"conclusion":"SUCCESS"}]},
    {"number":41,"title":"ci: image bump (new)","headRefName":"ci/image-bump-git-bbbb2222","createdAt":"2026-09-02T00:00:00Z","isDraft":false,"statusCheckRollup":[{"conclusion":"SUCCESS"}]}
  ]'
  run bash "$GUARD"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '#40 \[SUPERSEDED\]'
  echo "$output" | grep -q '#41 \[MERGEABLE\]'
  echo "$output" | grep -q 'ship'
  # image-bump verdicts must never consult the compare API (recreate is meaningless for them).
  not_called_with gh 'compare'
}

@test "ci/image-bump: --apply closes the older but NEVER recreates it (not dependabot's PR)" {
  stub_dispatch gh
  stub_case gh 'pr list' 0 '[
    {"number":40,"title":"ci: image bump (old)","headRefName":"ci/image-bump-git-aaaa1111","createdAt":"2026-09-01T00:00:00Z","isDraft":false,"statusCheckRollup":[{"conclusion":"SUCCESS"}]},
    {"number":41,"title":"ci: image bump (new)","headRefName":"ci/image-bump-git-bbbb2222","createdAt":"2026-09-02T00:00:00Z","isDraft":false,"statusCheckRollup":[{"conclusion":"SUCCESS"}]}
  ]'
  stub_case gh 'issues' 0 ''
  stub_case gh 'pulls'  0 ''
  run bash "$GUARD" --apply
  [ "$status" -eq 0 ]
  called_with gh 'pulls/40'
  not_called_with gh '@dependabot recreate'
  not_called_with gh 'merge'
}

@test "unknown argument fails closed (exit 2)" {
  stub_dispatch gh
  run bash "$GUARD" --wat
  [ "$status" -eq 2 ]
}

@test "the CronJob's embedded script is byte-identical to the tested guard (no drift)" {
  # k8s/pr-lifecycle/pr-lifecycle-reconcile.yaml carries a COPY of the guard inside its ConfigMap so the
  # in-cluster reconcile Job runs the same decision core these tests verify (incl. "--apply never merges").
  # The repo script is the source; scripts/embed-pr-lifecycle.sh regenerates the embedded copy. Two copies
  # would drift silently — and this one AUTO-MUTATES PRs, so a drifted copy is the worst place for it.
  local manifest="$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s/pr-lifecycle/pr-lifecycle-reconcile.yaml"
  [ -f "$manifest" ]
  awk '
    $0 == "  check-pr-lifecycle.sh: |" { grab=1; next }
    grab && $0 == "---" { grab=0 }
    grab { sub(/^    /, ""); print }
  ' "$manifest" > "$BATS_TEST_TMPDIR/embedded.sh"
  diff "$GUARD" "$BATS_TEST_TMPDIR/embedded.sh"
}
