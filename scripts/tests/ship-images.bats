#!/usr/bin/env bats
# Gate predicates and loop orchestration for scripts/ship-images.sh.
#
# The predicates are tested directly by sourcing the script with SHIP_IMAGES_LIB=1, which suppresses
# main(). The orchestration tests run main() with every external binary stubbed on PATH — no test in
# this file may merge a PR, trigger a pipeline, or touch the cluster.

setup() {
  load helper
  setup_stubs
  SHIP="$REPO_ROOT/scripts/ship-images.sh"
}

teardown() {
  teardown_stubs
}

# --- Gate predicates ------------------------------------------------------------------

@test "FR1.2 head_matches_origin: true when HEAD and origin/main agree" {
  stub git 0 'aaaaaaaabbbbbbbbccccccccdddddddd'
  SHIP_IMAGES_LIB=1 source "$SHIP"
  run head_matches_origin
  [ "$status" -eq 0 ]
}

@test "FR1.2 head_matches_origin: false when the local commit is unpushed" {
  # Two different shas: `git rev-parse HEAD` and `git rev-parse origin/main` disagree, which is what
  # an unpushed commit looks like. This is the gate the 2026-08-20 "triggered before the push
  # landed" failure needed and did not have.
  stub_seq git
  stub_seq_add git 0 'aaaaaaaabbbbbbbbccccccccdddddddd'
  stub_seq_add git 0 '11111111222222223333333344444444'
  SHIP_IMAGES_LIB=1 source "$SHIP"
  run head_matches_origin
  [ "$status" -ne 0 ]
}

@test "FR1.4 sha_differs_from_deployed: true when the deployed tag is older" {
  SHIP_IMAGES_LIB=1 source "$SHIP"
  run sha_differs_from_deployed 'git-9a4996c6' 'registry.weyland.lab/scan-suite:git-2c73c898'
  [ "$status" -eq 0 ]
}

@test "FR1.4 sha_differs_from_deployed: false when the deployed tag already matches" {
  SHIP_IMAGES_LIB=1 source "$SHIP"
  run sha_differs_from_deployed 'git-9a4996c6' 'registry.weyland.lab/scan-suite:git-9a4996c6'
  [ "$status" -ne 0 ]
}

@test "FR2.1 pr_commits_are_ci: true when every commit is authored by weyland-ci" {
  # The PR AUTHOR is always the PAT owner (edtbl76) — `weyland-ci` is not a GitHub account and never
  # will be. The real CI marker is the COMMIT author, which open-deploy-pr.sh sets via `git config`.
  # Found on the first live run 2026-08-22: FR2.1 as originally written was unsatisfiable.
  SHIP_IMAGES_LIB=1 source "$SHIP"
  stub gh 0 'weyland-ci'
  run pr_commits_are_ci 33
  [ "$status" -eq 0 ]
}

@test "FR2.1 pr_commits_are_ci: false when any commit is human-authored" {
  SHIP_IMAGES_LIB=1 source "$SHIP"
  stub gh 0 'weyland-ci
edtbl76'
  run pr_commits_are_ci 33
  [ "$status" -ne 0 ]
}

@test "FR2.1 pr_commits_are_ci: false when the commit list is empty (cannot verify != safe)" {
  SHIP_IMAGES_LIB=1 source "$SHIP"
  stub gh 0 ''
  run pr_commits_are_ci 33
  [ "$status" -ne 0 ]
}

@test "FR2.1 diff_is_tags_only: true for a diff of nothing but image-tag lines" {
  SHIP_IMAGES_LIB=1 source "$SHIP"
  run diff_is_tags_only "$FIXTURES/tags-only.diff"
  [ "$status" -eq 0 ]
}

@test "FR2.1 diff_is_tags_only: false when the diff also changes a resource limit" {
  # The dangerous case: a real change smuggled into a bump PR. The diff still contains a tag line,
  # so anything that merely LOOKS FOR one would pass it.
  SHIP_IMAGES_LIB=1 source "$SHIP"
  run diff_is_tags_only "$FIXTURES/mixed.diff"
  [ "$status" -ne 0 ]
}

@test "FR4.2 is_image_bump_branch: recognises the CI branch shape and nothing else" {
  SHIP_IMAGES_LIB=1 source "$SHIP"
  run is_image_bump_branch 'ci/image-bump-9a4996c6'
  [ "$status" -eq 0 ]
  run is_image_bump_branch 'main'
  [ "$status" -ne 0 ]
  run is_image_bump_branch 'feature/ci-image-bump-thing'
  [ "$status" -ne 0 ]
}

# --- Loop orchestration ---------------------------------------------------------------
# Every one of these runs the real script end to end with `git`, `gh`, `woodpecker-cli`, `argocd`
# and `kubectl` replaced by stubs. The assertions that matter most are the negative ones — proving
# the script REFUSED to merge or sync, not merely that it happened not to.

# git answers used by a run that should get past the FR1.2 gate.
stub_git_pushed() {
  stub_dispatch git
  stub_case git 'rev-parse --short=8' 0 '9a4996c6'
  stub_case git 'rev-parse' 0 'aaaaaaaabbbbbbbbccccccccdddddddd'
  stub_case git 'push --delete' 0 ''
}

@test "FR1.2/FR4.1 aborts before triggering anything when HEAD is unpushed" {
  stub_dispatch git
  stub_case git 'rev-parse HEAD' 0 'aaaaaaaabbbbbbbbccccccccdddddddd'
  stub_case git 'rev-parse origin/main' 0 '11111111222222223333333344444444'
  stub_dispatch woodpecker-cli
  run bash "$SHIP"
  [ "$status" -ne 0 ]
  # FR4.1: abort, do not continue. Nothing may have been triggered.
  never_called woodpecker-cli
}

@test "FR1.6 names the gate that stopped the run" {
  stub_dispatch git
  stub_case git 'rev-parse HEAD' 0 'aaaaaaaabbbbbbbbccccccccdddddddd'
  stub_case git 'rev-parse origin/main' 0 '11111111222222223333333344444444'
  run bash "$SHIP"
  [ "$status" -ne 0 ]
  [[ "$output" == *"FR1.2"* ]]
}

@test "FR1.3 surfaces the failing step's log rather than a bare status" {
  stub_git_pushed
  stub_dispatch woodpecker-cli
  stub_case woodpecker-cli 'pipeline create' 0 '42 pending'
  stub_case woodpecker-cli 'pipeline show' 0 '42 failure'
  stub_case woodpecker-cli 'log' 0 'buildctl: failed to solve: unpigz invalid deflate'
  stub_dispatch kubectl
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-2c73c898'
  run bash "$SHIP"
  [ "$status" -ne 0 ]
  [[ "$output" == *"unpigz invalid deflate"* ]]
}

@test "FR1.3 polls until the pipeline reaches a terminal state" {
  stub_git_pushed
  stub_dispatch kubectl
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-2c73c898'
  # gh and argocd are stubbed even though this test asserts nothing about them: an unstubbed binary
  # here would reach the real GitHub API and the real cluster.
  stub_dispatch gh
  stub_dispatch argocd
  stub_seq woodpecker-cli
  stub_seq_add woodpecker-cli 0 '42 pending'
  stub_seq_add woodpecker-cli 0 '42 running'
  stub_seq_add woodpecker-cli 0 '42 running'
  stub_seq_add woodpecker-cli 0 '42 success'
  SHIP_POLL_INTERVAL=0 run bash "$SHIP"
  # It must have looked more than once — a single check is not polling.
  [ "$(calls_to woodpecker-cli | grep -c 'pipeline show')" -ge 2 ]
}

@test "FR2.2 refuses to merge a PR that is not CI-authored, and says which condition failed" {
  stub_git_pushed
  stub_dispatch woodpecker-cli
  stub_case woodpecker-cli 'pipeline create' 0 '42 pending'
  stub_case woodpecker-cli 'pipeline show' 0 '42 success'
  stub_dispatch gh
  stub_case gh 'pr list' 0 '13	ci/image-bump-9a4996c6	edtbl76'
  stub_case gh 'pr view' 0 'edtbl76'
  stub_case gh 'pr diff' 0 "$(cat "$FIXTURES/tags-only.diff")"
  stub_dispatch kubectl
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-2c73c898'
  run bash "$SHIP"
  [ "$status" -ne 0 ]
  [[ "$output" == *"FR2.1"* ]]
  # The assertion that matters: no merge was attempted.
  ! called_with gh 'pr merge'
}

@test "FR2.2 refuses to merge when the diff carries more than image-tag lines" {
  stub_git_pushed
  stub_dispatch woodpecker-cli
  stub_case woodpecker-cli 'pipeline create' 0 '42 pending'
  stub_case woodpecker-cli 'pipeline show' 0 '42 success'
  stub_dispatch gh
  stub_case gh 'pr list' 0 '13	ci/image-bump-9a4996c6	weyland-ci'
  stub_case gh 'pr view' 0 'weyland-ci'
  stub_case gh 'pr diff' 0 "$(cat "$FIXTURES/mixed.diff")"
  stub_dispatch kubectl
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-2c73c898'
  run bash "$SHIP"
  [ "$status" -ne 0 ]
  ! called_with gh 'pr merge'
}

@test "FR2.3 closes a superseded older bump before merging the newer one" {
  stub_git_pushed
  stub_dispatch woodpecker-cli
  stub_case woodpecker-cli 'pipeline create' 0 '42 pending'
  stub_case woodpecker-cli 'pipeline show' 0 '42 success'
  stub_dispatch gh
  # Two open bumps. #12 is the older one; merging it after #13 rolls images BACKWARDS.
  stub_case gh 'pr list' 0 '13	ci/image-bump-9a4996c6	weyland-ci
12	ci/image-bump-2c73c898	weyland-ci'
  stub_case gh 'pr view' 0 'weyland-ci'
  stub_case gh 'pr diff' 0 "$(cat "$FIXTURES/tags-only.diff")"
  stub_dispatch argocd
  stub_dispatch kubectl
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-9a4996c6'
  run bash "$SHIP"
  called_with gh 'pr close 12'
  ! called_with gh 'pr close 13'
}

@test "FR4.2/FR4.3 deletes the orphan branch on abort and still reports the gate, not the cleanup" {
  stub_git_pushed
  stub_dispatch woodpecker-cli
  stub_case woodpecker-cli 'pipeline create' 0 '42 pending'
  stub_case woodpecker-cli 'pipeline show' 0 '42 failure'
  stub_case woodpecker-cli 'log' 0 'step build failed'
  stub_dispatch kubectl
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-2c73c898'
  run bash "$SHIP"
  [ "$status" -ne 0 ]
  called_with git 'push --delete origin ci/image-bump-9a4996c6'
  # FR4.3 — the reported reason is the gate, not the cleanup.
  [[ "$output" == *"FR1.3"* ]]
}

@test "FR1.5/NFR4 syncs only the affected app and verifies against the live resource" {
  stub_git_pushed
  stub_dispatch woodpecker-cli
  stub_case woodpecker-cli 'pipeline create' 0 '42 pending'
  stub_case woodpecker-cli 'pipeline show' 0 '42 success'
  stub_dispatch gh
  stub_case gh 'pr list' 0 '13	ci/image-bump-9a4996c6	weyland-ci'
  stub_case gh 'pr view' 0 'weyland-ci'
  stub_case gh 'pr diff' 0 "$(cat "$FIXTURES/tags-only.diff")"
  stub_dispatch argocd
  # The cluster runs the OLD tag until the merge lands, and the new one after. Modelling that is
  # what lets FR1.4 (there is something to deploy) and FR1.5 (it deployed) both mean something.
  stub_when_seen kubectl 'pr merge' \
    'registry.weyland.lab/scan-suite:git-2c73c898' \
    'registry.weyland.lab/scan-suite:git-9a4996c6'
  run bash "$SHIP"
  [ "$status" -eq 0 ]
  # NFR4: never a blanket refresh across all 78 applications.
  ! called_with argocd '--all'
  # FR1.5: the rollout was asserted against the cluster, not against the repo or the PR.
  called_with kubectl 'get'
}

@test "NFR3 a re-run after a successful ship is a no-op that reports already deployed" {
  stub_git_pushed
  stub_dispatch woodpecker-cli
  stub_dispatch gh
  stub_dispatch argocd
  stub_dispatch kubectl
  # The live cluster already carries the tag HEAD would produce.
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-9a4996c6'
  run bash "$SHIP"
  [ "$status" -eq 0 ]
  [[ "$output" == *"already deployed"* ]]
  never_called woodpecker-cli
  never_called argocd
}

@test "FR4.2 does NOT delete the branch once a valid PR exists" {
  # THE BUG THAT CLOSED PR #33 (2026-08-22, first live run): ORPHAN_BRANCH was set at trigger time and
  # only cleared after MERGE, so aborting anywhere between "PR opened" and "merged" deleted the branch
  # of a perfectly good PR — and GitHub auto-closes a PR when its head branch goes. FR4.2 means a branch
  # pushed WITHOUT a PR. A branch with an open PR is not an orphan.
  stub_git_pushed
  stub_dispatch woodpecker-cli
  stub_case woodpecker-cli 'pipeline create' 0 '42 pending'
  stub_case woodpecker-cli 'pipeline show' 0 '42 success'
  stub_dispatch gh
  stub_case gh 'pr list' 0 '13	ci/image-bump-9a4996c6	edtbl76'
  stub_case gh 'pr view' 0 'edtbl76'          # human-authored -> FR2.1 aborts AFTER the PR was found
  stub_case gh 'pr diff' 0 "$(cat "$FIXTURES/tags-only.diff")"
  stub_dispatch kubectl
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-2c73c898'
  run bash "$SHIP"
  [ "$status" -ne 0 ]
  ! called_with git 'push --delete'
}

@test "FR1.6 a gate failure reads as a failure, not as the assertion it tested" {
  # "stopped at FR2.1 — PR #33 is CI-authored" read as if the check had PASSED.
  stub_dispatch git
  stub_case git 'rev-parse HEAD' 0 'aaaaaaaabbbbbbbbccccccccdddddddd'
  stub_case git 'rev-parse origin/main' 0 '11111111222222223333333344444444'
  run bash "$SHIP"
  [[ "$output" == *"expected"* ]]
}
