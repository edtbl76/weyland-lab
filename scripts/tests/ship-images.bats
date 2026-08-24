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

  # Default: the detector reports work, which is what every orchestration test assumes when it
  # expects a pipeline to be triggered. Without this the suite runs the REAL detect-changes.sh
  # against the live repo, and on a quiet day every test short-circuits at "nothing to ship" and
  # passes for the wrong reason. The one test that wants an empty plan overrides SHIP_DETECT itself.
  printf '#!/usr/bin/env bash\nprintf "scan-suite\\tservices/scan-suite\\tgit-9a4996c6\\tk8s/x.yaml\\n" > "$PLAN"\n' \
    > "$STUB_DIR/detect-work"
  chmod +x "$STUB_DIR/detect-work"
  export SHIP_DETECT="$STUB_DIR/detect-work"
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
  stub_case gh 'isCrossRepository' 0 'false'
  stub_case gh 'pr view' 0 'edtbl76'
  stub_case gh 'pr diff' 0 "$(cat "$FIXTURES/tags-only.diff")"
  stub_dispatch kubectl
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-2c73c898'
  run bash "$SHIP"
  [ "$status" -ne 0 ]
  [[ "$output" == *"FR2.1"* ]]
  # The assertion that matters: no merge was attempted.
  not_called_with gh 'pr merge'
}

@test "FR2.2 refuses to merge when the diff carries more than image-tag lines" {
  stub_git_pushed
  stub_dispatch woodpecker-cli
  stub_case woodpecker-cli 'pipeline create' 0 '42 pending'
  stub_case woodpecker-cli 'pipeline show' 0 '42 success'
  stub_dispatch gh
  stub_case gh 'pr list' 0 '13	ci/image-bump-9a4996c6	weyland-ci'
  stub_case gh 'isCrossRepository' 0 'false'
  stub_case gh 'pr view' 0 'weyland-ci'
  stub_case gh 'pr diff' 0 "$(cat "$FIXTURES/mixed.diff")"
  stub_dispatch kubectl
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-2c73c898'
  run bash "$SHIP"
  [ "$status" -ne 0 ]
  not_called_with gh 'pr merge'
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
  stub_case gh 'isCrossRepository' 0 'false'
  stub_case gh 'pr view' 0 'weyland-ci'
  stub_case gh 'pr diff' 0 "$(cat "$FIXTURES/tags-only.diff")"
  stub_dispatch argocd
  stub_dispatch kubectl
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-9a4996c6'
  run bash "$SHIP"
  called_with gh 'pr close 12'
  not_called_with gh 'pr close 13'
}

@test "FR4.2/FR4.3 deletes the orphan branch on abort and still reports the gate, not the cleanup" {
  stub_git_pushed
  stub_dispatch woodpecker-cli
  stub_case woodpecker-cli 'pipeline create' 0 '42 pending'
  stub_case woodpecker-cli 'pipeline show' 0 '42 failure'
  stub_case woodpecker-cli 'log' 0 'step build failed'
  # gh MUST be stubbed: cleanup now asks GitHub whether the branch backs an open PR, and an
  # unstubbed `gh` would reach the real api.github.com from a test suite that guarantees it
  # touches nothing outside its container. No case registered => empty answer => no PR => delete,
  # which is this test's intent.
  stub_dispatch gh
  stub_dispatch kubectl
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-2c73c898'
  run bash "$SHIP"
  [ "$status" -ne 0 ]
  called_with git 'push --delete origin ci/image-bump-9a4996c6'
  # FR4.3 — the reported reason is the gate, not the cleanup.
  [[ "$output" == *"FR1.3"* ]]
}

@test "FR4.2 does NOT delete the branch when it already backs an open PR" {
  # 2026-08-24, and it survived only by luck. The run aborted at FR1.3 — AFTER deploy-handoff had
  # opened PR #36, but BEFORE the step that looks the PR up. ORPHAN_BRANCH is set right after the
  # trigger and cleared only once a valid PR is found, so cleanup fired against the branch backing
  # a real, mergeable PR and printed "deleting orphan branch ci/image-bump-dab283e9". The delete
  # failed ONLY because the ISP was down at that moment.
  #
  # The existing "does NOT delete once a valid PR exists" test covers aborts AFTER the lookup. The
  # window between "the pipeline opened a PR" and "we noticed it" was uncovered, and that is exactly
  # where this run died.
  stub_git_pushed
  stub_dispatch woodpecker-cli
  stub_case woodpecker-cli 'pipeline create' 0 '42 pending'
  stub_case woodpecker-cli 'pipeline show' 0 '42 failure'
  stub_case woodpecker-cli 'log' 0 'step build failed'
  stub_dispatch gh
  stub_case gh 'pr list' 0 '42'
  stub_dispatch kubectl
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-2c73c898'
  run bash "$SHIP"
  [ "$status" -ne 0 ]
  # THE ASSERTION: the branch survives.
  not_called_with git 'push --delete'
  [[ "$output" == *"open PR"* ]]
  # FR4.3 still holds — the reported reason is the gate.
  [[ "$output" == *"FR1.3"* ]]
}

@test "FR4.2 keeps the branch when GitHub cannot be asked — fail closed" {
  # The costs are wildly asymmetric. A wrong "no PR" DELETES the run's own output; a wrong "yes"
  # leaves a branch the staleness watchdog will surface. So the unknown case must take the safe
  # side. Getting this backwards would reproduce the whole silent-failure family this loop exists
  # to prevent — an unanswerable query read as a negative answer.
  stub_git_pushed
  stub_dispatch woodpecker-cli
  stub_case woodpecker-cli 'pipeline create' 0 '42 pending'
  stub_case woodpecker-cli 'pipeline show' 0 '42 failure'
  stub_case woodpecker-cli 'log' 0 'step build failed'
  # gh cannot answer at all.
  printf '#!/usr/bin/env bash\nprintf "gh %%s\\n" "$*" >> "%s"\necho "error connecting to api.github.com" >&2\nexit 1\n' \
    "$STUB_LOG" > "$STUB_DIR/gh"
  chmod +x "$STUB_DIR/gh"
  stub_dispatch kubectl
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-2c73c898'
  run bash "$SHIP"
  [ "$status" -ne 0 ]
  not_called_with git 'push --delete'
  [[ "$output" == *"cannot ask GitHub"* ]]
}

@test "FR1.5/NFR4 syncs only the affected app and verifies against the live resource" {
  stub_git_pushed
  stub_dispatch woodpecker-cli
  stub_case woodpecker-cli 'pipeline create' 0 '42 pending'
  stub_case woodpecker-cli 'pipeline show' 0 '42 success'
  stub_dispatch gh
  stub_case gh 'pr list' 0 '13	ci/image-bump-9a4996c6	weyland-ci'
  stub_case gh 'isCrossRepository' 0 'false'
  stub_case gh 'pr view' 0 'weyland-ci'
  stub_case gh 'pr diff' 0 "$(cat "$FIXTURES/tags-only.diff")"
  stub_dispatch argocd
  # The cluster runs the OLD tag until the merge lands, and the new one after. Modelling that is
  # what lets FR1.4 (there is something to deploy) and FR1.5 (it deployed) both mean something.
  stub_when_seen kubectl 'pr merge' \
    'registry.weyland.lab/scan-suite:git-2c73c898 registry.weyland.lab/weyland-flink:git-2c73c898' \
    'registry.weyland.lab/scan-suite:git-9a4996c6 registry.weyland.lab/weyland-flink:git-9a4996c6'
  run bash "$SHIP"
  [ "$status" -eq 0 ]
  # NFR4: never a blanket refresh across all 78 applications.
  not_called_with argocd '--all'
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
  stub_case gh 'isCrossRepository' 0 'false'
  stub_case gh 'pr view' 0 'edtbl76'          # human-authored -> FR2.1 aborts AFTER the PR was found
  stub_case gh 'pr diff' 0 "$(cat "$FIXTURES/tags-only.diff")"
  stub_dispatch kubectl
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-2c73c898'
  run bash "$SHIP"
  [ "$status" -ne 0 ]
  not_called_with git 'push --delete'
}

@test "FR1.6 a gate failure reads as a failure, not as the assertion it tested" {
  # "stopped at FR2.1 — PR #33 is CI-authored" read as if the check had PASSED.
  stub_dispatch git
  stub_case git 'rev-parse HEAD' 0 'aaaaaaaabbbbbbbbccccccccdddddddd'
  stub_case git 'rev-parse origin/main' 0 '11111111222222223333333344444444'
  run bash "$SHIP"
  [[ "$output" == *"expected"* ]]
}

@test "FR2.1 pr_is_same_repo: rejects a PR opened from a fork" {
  # SECURITY. The commit author is SELF-ASSERTED — anyone can `git config user.name weyland-ci`.
  # weyland-lab is public and has no branch protection, so a stranger could fork it, branch
  # `ci/image-bump-<current-main-sha>`, commit a tags-only diff under that name, and this loop would
  # merge it to main. GitHub decides isCrossRepository, so it cannot be spoofed; CI always pushes to
  # the BASE repo, so a fork PR is never CI's.
  SHIP_IMAGES_LIB=1 source "$SHIP"
  stub gh 0 'false'
  run pr_is_same_repo 34
  [ "$status" -eq 0 ]
  stub gh 0 'true'
  run pr_is_same_repo 34
  [ "$status" -ne 0 ]
}

@test "FR2.1 pr_is_same_repo: fails closed when the answer is unreadable" {
  SHIP_IMAGES_LIB=1 source "$SHIP"
  stub gh 0 ''
  run pr_is_same_repo 34
  [ "$status" -ne 0 ]
}

# --- The two defects the first successful live run exposed ------------------------------

@test "FR1.5 verifies EVERY bumped image, not just one" {
  # THE BUG THAT PRINTED A FALSE SUCCESS (2026-08-22): live_carries_tag grepped ALL pods for the tag,
  # so one match passed the gate. dagster-user-code had git-36c4d3e0 and weyland-tool-server did not,
  # and the command still said "shipped — git-36c4d3e0 is live". A verification gate that passes on a
  # partial rollout is the exact false-confidence failure this whole effort exists to remove.
  SHIP_IMAGES_LIB=1 source "$SHIP"
  stub_dispatch kubectl
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-9a4996c6
registry.weyland.lab/weyland-flink:git-2c73c898'
  run all_bumped_images_live 'git-9a4996c6' "$FIXTURES/tags-only.diff"
  [ "$status" -ne 0 ]                       # weyland-flink is stale -> must FAIL
  [[ "$output" == *"weyland-flink"* ]]      # and must name which one
}

@test "FR1.5 passes only when every bumped image carries the tag" {
  SHIP_IMAGES_LIB=1 source "$SHIP"
  stub_dispatch kubectl
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-9a4996c6
registry.weyland.lab/weyland-flink:git-9a4996c6'
  run all_bumped_images_live 'git-9a4996c6' "$FIXTURES/tags-only.diff"
  [ "$status" -eq 0 ]
}

@test "NFR4 affected_apps distinguishes the 12 loose apps that share one path" {
  # They all declare `path: .../k8s` and differ only by `directory.include` globs. Longest-prefix
  # matching cannot tell them apart, so weyland-tool-server.yaml resolved to `postgres` and the
  # tool-server app was never synced.
  SHIP_IMAGES_LIB=1 source "$SHIP"
  run affected_apps "$FIXTURES/loose-file.diff"
  [[ "$output" == *"weyland-tool-server"* ]]
  [[ "$output" != *"postgres"* ]]
}

@test "FR1.5 ignores a COMPLETED JOB's pod still carrying the old tag" {
  # 2026-08-24, live: the loop merged PR #37, every workload really was on git-afb1fb5d, and FR1.5
  # still failed with `not yet on git-afb1fb5d: scan-suite(git-ef734fc8)`. What it had read was
  #
  #   weyland/Job/code-scan-suite-29791500   scan-suite:git-ef734fc8
  #   weyland/Job/scan-suite-adhoc           scan-suite:git-ef734fc8
  #
  # A Job's pod template is IMMUTABLE, so its finished pod carries its creation-time image forever.
  # `deployed_tag_for` grepped every pod and took `head -n1`, so an arbitrary historical record
  # outvoted the live workload — and the gate would have failed on scan-suite permanently, for as
  # long as those Job objects existed. Same "some pod somewhere" class as the partial-rollout bug
  # this gate replaced, just inverted: some pod somewhere has an OLD tag.
  SHIP_IMAGES_LIB=1 source "$SHIP"
  stub_dispatch kubectl
  stub_case kubectl 'status.phase=Running' 0 'registry.weyland.lab/scan-suite:git-9a4996c6
registry.weyland.lab/weyland-flink:git-9a4996c6'
  stub_case kubectl 'get cronjob' 0 ''
  # What `kubectl get pods -A` actually returns today — the finished Job pod listed FIRST, which is
  # exactly what head -n1 picked up.
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-ef734fc8
registry.weyland.lab/scan-suite:git-9a4996c6
registry.weyland.lab/weyland-flink:git-9a4996c6'
  run all_bumped_images_live 'git-9a4996c6' "$FIXTURES/tags-only.diff"
  [ "$status" -eq 0 ]
}

@test "FR1.5 verifies a CronJob-only image from its template, not from pods" {
  # scan-suite runs ONLY as a weekly CronJob, so between runs it has NO pod at all. A pod-only check
  # cannot verify it in principle — it would read `absent` and fail every time outside the ~minutes
  # the job is actually executing. The CronJob's own pod template IS the deployed state for it.
  # smoke_ok already treats Job-shaped images specially; FR1.5 did not.
  SHIP_IMAGES_LIB=1 source "$SHIP"
  stub_dispatch kubectl
  stub_case kubectl 'status.phase=Running' 0 'registry.weyland.lab/weyland-flink:git-9a4996c6'
  stub_case kubectl 'get cronjob' 0 'registry.weyland.lab/scan-suite:git-9a4996c6'
  stub_case kubectl 'get' 0 'registry.weyland.lab/weyland-flink:git-9a4996c6'
  run all_bumped_images_live 'git-9a4996c6' "$FIXTURES/tags-only.diff"
  [ "$status" -eq 0 ]
}

@test "FR1.5 still fails when a RUNNING pod carries an old tag" {
  # The control for the two tests above. Without it, a fix that simply stopped looking at anything
  # would pass them both while verifying nothing — which is the failure mode this gate exists for.
  SHIP_IMAGES_LIB=1 source "$SHIP"
  stub_dispatch kubectl
  stub_case kubectl 'status.phase=Running' 0 'registry.weyland.lab/scan-suite:git-2c73c898
registry.weyland.lab/weyland-flink:git-2c73c898'
  stub_case kubectl 'get cronjob' 0 ''
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-2c73c898
registry.weyland.lab/weyland-flink:git-2c73c898'
  run all_bumped_images_live 'git-9a4996c6' "$FIXTURES/tags-only.diff"
  [ "$status" -ne 0 ]
  [[ "$output" == *"weyland-flink"* ]]
}

@test "FR1.5 fails closed when the bumped-image list cannot be read" {
  # Nearly shipped as another false green: `rm -f "$diff_file"` ran BEFORE this gate, so the image
  # list came back empty, the loop never executed, nothing was marked stale, and the gate PASSED —
  # declaring a rollout verified without checking a single image. Empty input is not success.
  SHIP_IMAGES_LIB=1 source "$SHIP"
  stub_dispatch kubectl
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-9a4996c6'
  run all_bumped_images_live 'git-9a4996c6' /nonexistent/diff
  [ "$status" -ne 0 ]
}

# --- SMOKE -------------------------------------------------------------------------------------
#
# FR1.5 proves the right BYTES are on the node. It says nothing about whether the process works.
# `Ready` is only evidence when a probe measured something: with no readinessProbe a pod reports
# 1/1 Ready the instant PID 1 is alive. dagster-user-code had exactly that on 2026-08-23 — the gRPC
# code server every Dagster run executes inside could fail to load its definitions and this loop
# would still print "✓ shipped". These tests pin the gate that closes it.

# smoke_rows <image-a-probe-state> <image-b-probe-state> — build a workload table the stub returns.
# Columns: namespace, name, image, probe|NOPROBE, desired, available.
smoke_rows() {
  printf 'code-quality\tscan-suite\tregistry.weyland.lab/scan-suite:git-9a4996c6\t%s\t1\t%s\n' "$1" "${3:-1}"
  printf 'data-mesh\tweyland-flink\tregistry.weyland.lab/weyland-flink:git-9a4996c6\t%s\t1\t%s\n' "$2" "${4:-1}"
}

@test "SMOKE fails and names the workload when a bumped image declares no readinessProbe" {
  SHIP_IMAGES_LIB=1 source "$SHIP"
  stub_dispatch kubectl
  stub_case kubectl 'get deploy' 0 "$(smoke_rows probe NOPROBE)"
  run smoke_ok 'git-9a4996c6' "$FIXTURES/tags-only.diff"
  [ "$status" -ne 0 ]
  [[ "$output" == *"weyland-flink"* ]]        # must name WHICH workload is unmeasured
  [[ "$output" != *"scan-suite"*"no readiness"* ]]
}

@test "SMOKE fails and names the workload when replicas are not all available" {
  SHIP_IMAGES_LIB=1 source "$SHIP"
  stub_dispatch kubectl
  stub_case kubectl 'get deploy' 0 "$(smoke_rows probe probe 1 0)"
  run smoke_ok 'git-9a4996c6' "$FIXTURES/tags-only.diff"
  [ "$status" -ne 0 ]
  [[ "$output" == *"weyland-flink"* ]]
  [[ "$output" == *"0/1"* ]]
}

@test "SMOKE passes when every workload for every bumped image is probe-backed and available" {
  SHIP_IMAGES_LIB=1 source "$SHIP"
  stub_dispatch kubectl
  stub_case kubectl 'get deploy' 0 "$(smoke_rows probe probe)"
  run smoke_ok 'git-9a4996c6' "$FIXTURES/tags-only.diff"
  [ "$status" -eq 0 ]
}

@test "SMOKE fails closed when the workload table comes back empty" {
  # Same class as the FR1.5 empty-input bug: an empty table means every loop body is skipped, nothing
  # is marked bad, and the gate would pass having measured nothing. kubectl returning no rows is a
  # failure to observe, never an observation of health.
  SHIP_IMAGES_LIB=1 source "$SHIP"
  stub_dispatch kubectl
  stub_case kubectl 'get deploy' 0 ''
  run smoke_ok 'git-9a4996c6' "$FIXTURES/tags-only.diff"
  [ "$status" -ne 0 ]
  # Assert the REASON, not just non-zero: a missing function also exits non-zero, so a status-only
  # assertion passes against no implementation at all. This test caught exactly that on itself.
  [[ "$output" == *"refusing to call that smoke-verified"* ]]
}

@test "SMOKE reports an image with no matching workload rather than silently passing it" {
  # scan-suite is a CI image — it runs as a Job, not a Deployment. That is legitimate, so it must not
  # fail the gate, but it must be NAMED as unchecked so the run never implies coverage it lacks.
  SHIP_IMAGES_LIB=1 source "$SHIP"
  stub_dispatch kubectl
  stub_case kubectl 'get deploy' 0 "$(printf 'data-mesh\tweyland-flink\tregistry.weyland.lab/weyland-flink:git-9a4996c6\tprobe\t1\t1\n')"
  run smoke_ok 'git-9a4996c6' "$FIXTURES/tags-only.diff"
  [ "$status" -eq 0 ]
  [[ "$output" == *"scan-suite"* ]]
  [[ "$output" == *"no workload"* ]]
}

@test "NFR3 exits cleanly when no image context changed — without triggering a pipeline" {
  # Running the loop after a docs- or script-only commit used to trigger a pointless build and then
  # ABORT at FR1.4 ("succeeded but opened no PR"), because "no PR because nothing changed" and "no PR
  # because deploy-handoff broke" looked identical. They are not the same, and only one is a fault.
  stub_git_pushed
  stub_dispatch woodpecker-cli
  stub_dispatch gh
  stub_dispatch kubectl
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-2c73c898'
  # a detector that finds nothing to build
  printf '#!/usr/bin/env bash\n: > "$PLAN"\n' > "$STUB_DIR/detect-none"
  chmod +x "$STUB_DIR/detect-none"
  SHIP_DETECT="$STUB_DIR/detect-none" run bash "$SHIP"
  [ "$status" -eq 0 ]
  [[ "$output" == *"nothing to ship"* ]]
  never_called woodpecker-cli
}

@test "DETECT a failing detector aborts with its reason — never 'nothing to ship'" {
  # 2026-08-24: run from a subdirectory, detect-changes.sh could not find its own images.tsv. The
  # loop reported "✓ nothing to ship" and exited 0 while three images were genuinely stale.
  #
  # detect-changes.sh has been fixed to fail closed, but that only helps if the CALLER looks. This
  # step ran it as `>/dev/null 2>&1`, so the one line of evidence ("grep: scripts/ci/images.tsv: No
  # such file or directory") was discarded before anyone could read it. An empty plan from a
  # detector that FAILED is not the same fact as an empty plan from a detector that SUCCEEDED, and
  # the loop must not collapse the two.
  stub_git_pushed
  stub_dispatch woodpecker-cli
  stub_dispatch gh
  stub_dispatch kubectl
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-2c73c898'
  printf '#!/usr/bin/env bash\n: > "$PLAN"\necho "detect: images.tsv unreadable — refusing" >&2\nexit 1\n' \
    > "$STUB_DIR/detect-broken"
  chmod +x "$STUB_DIR/detect-broken"
  SHIP_DETECT="$STUB_DIR/detect-broken" run bash "$SHIP"
  [ "$status" -ne 0 ]
  # The REASON, not merely a non-zero exit — a bare status check passes on exit 127.
  [[ "$output" == *"DETECT"* ]]
  [[ "$output" != *"nothing to ship"* ]]
  # The detector's own words must survive to the operator.
  [[ "$output" == *"refusing"* ]]
  # And a run that cannot tell whether work exists must not start a build.
  never_called woodpecker-cli
}

# --- FR1.3 trigger: the CLI failing must be a REPORTED failure, not a silent exit ------
#
# 2026-08-24, immediately after the DETECT fix: the loop reached "→ triggering pipeline" and then
# returned to the prompt with no pipeline number, no gate line, and no error. Under
# `set -euo pipefail`,
#
#     num="$(woodpecker-cli pipeline create ... 2>/dev/null | wp_field 1)"
#
# is a bare assignment in main(). When woodpecker-cli exits non-zero, `pipefail` makes the whole
# pipeline non-zero, `set -e` kills the script THERE, and the `[ -n "$num" ]` guard on the very next
# line never runs — so the one guard written for this failure was unreachable in the exact case it
# names. `2>/dev/null` had already discarded the reason. No pipeline was created; the operator saw
# a clean prompt.

@test "FR1.3 a failing woodpecker-cli aborts with its reason, not a silent exit" {
  stub_git_pushed
  stub_dispatch gh
  stub_dispatch kubectl
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-2c73c898'
  printf '#!/usr/bin/env bash\nprintf "woodpecker-cli %%s\\n" "$*" >> "%s"\necho "Error: client credentials not set" >&2\nexit 1\n' \
    "$STUB_LOG" > "$STUB_DIR/woodpecker-cli"
  chmod +x "$STUB_DIR/woodpecker-cli"
  WOODPECKER_TOKEN=t SHIP_ENV_FILE=/nonexistent run bash "$SHIP"
  [ "$status" -ne 0 ]
  # The gate must be NAMED. A bare non-zero check passes on the silent-exit bug itself.
  [[ "$output" == *"FR1.3"* ]]
  # And the CLI's own words must reach the operator rather than /dev/null.
  [[ "$output" == *"client credentials not set"* ]]
}

@test "FR1.3 aborts when the CLI succeeds but prints a table instead of a pipeline number" {
  # `--output json` is accepted and SILENTLY IGNORED by woodpecker-cli v3 — you get the human table
  # with exit 0. Field 1 of its first row is a header word, not a number; accepting it would poll a
  # pipeline that does not exist until the 30m timeout.
  stub_git_pushed
  stub_dispatch gh
  stub_dispatch kubectl
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-2c73c898'
  stub_dispatch woodpecker-cli
  stub_case woodpecker-cli 'pipeline create' 0 'NUMBER  STATUS'
  # Bounded on purpose. Before the fix a non-numeric "number" is accepted and polled to the full
  # timeout, so an unbounded Red run hangs instead of failing. SHIP_POLL_INTERVAL=0 does NOT bound
  # it — the counter only ever advances from 0 to 1 and then stalls there.
  SHIP_POLL_INTERVAL=1 SHIP_POLL_TIMEOUT=1 WOODPECKER_TOKEN=t SHIP_ENV_FILE=/nonexistent run bash "$SHIP"
  [ "$status" -ne 0 ]
  [[ "$output" == *"FR1.3"* ]]
}

@test "FR1.3 names the missing credential when WOODPECKER_TOKEN is unset" {
  # The actual 2026-08-24 cause: run from a directory whose .env holds Port credentials, with
  # scripts/.env never sourced. Saying so beats making the operator re-derive it.
  stub_git_pushed
  stub_dispatch gh
  stub_dispatch kubectl
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-2c73c898'
  printf '#!/usr/bin/env bash\nprintf "woodpecker-cli %%s\\n" "$*" >> "%s"\nexit 1\n' \
    "$STUB_LOG" > "$STUB_DIR/woodpecker-cli"
  chmod +x "$STUB_DIR/woodpecker-cli"
  WOODPECKER_TOKEN= SHIP_ENV_FILE=/nonexistent run bash "$SHIP"
  [ "$status" -ne 0 ]
  [[ "$output" == *"WOODPECKER_TOKEN"* ]]
}

# --- credentials come from the repo, not from the caller's shell ----------------------

@test "loads the env file so the loop does not depend on the caller having sourced it" {
  # woodpecker-cli reads .env from its WORKING DIRECTORY. Now that the loop runs correctly from any
  # directory, that is a live hazard: run from tofu/port and the CLI loads Port's .env, which has no
  # WOODPECKER_* keys at all. The loop loads the repo's own env file instead of hoping.
  stub_git_pushed
  stub_dispatch gh
  stub_dispatch kubectl
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-2c73c898'
  ENVFILE="$STUB_DIR/fixture.env"
  printf 'WOODPECKER_SERVER=http://mother:30980\nWOODPECKER_TOKEN=fixture-token\n' > "$ENVFILE"
  printf '#!/usr/bin/env bash\necho "TOKENSEEN=${WOODPECKER_TOKEN:-none}" >> "%s"\nexit 1\n' \
    "$STUB_LOG" > "$STUB_DIR/woodpecker-cli"
  chmod +x "$STUB_DIR/woodpecker-cli"
  WOODPECKER_TOKEN= WOODPECKER_SERVER= SHIP_ENV_FILE="$ENVFILE" run bash "$SHIP"
  grep -q 'TOKENSEEN=fixture-token' "$STUB_LOG"
}

@test "a missing env file is not fatal — the caller may have sourced it already" {
  stub_git_pushed
  stub_dispatch gh
  stub_dispatch kubectl
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-2c73c898'
  stub_dispatch woodpecker-cli
  stub_case woodpecker-cli 'pipeline create' 0 '41 pending'
  stub_case woodpecker-cli 'pipeline show'   0 '41 success'
  SHIP_POLL_INTERVAL=0 WOODPECKER_TOKEN=t SHIP_ENV_FILE=/nonexistent run bash "$SHIP"
  # It must get PAST the trigger — the absent file must not abort the run.
  [[ "$output" == *"pipeline #41"* ]]
}

@test "FR1.3 gives up with a reason when the CLI keeps failing while polling" {
  # Same shape one level down: poll_pipeline read `status` from a pipeline whose CLI half could
  # fail. An empty status is treated as non-terminal, so a dead CLI looked exactly like a slow
  # build — for the full 30-minute timeout — and then reported "ended as: unknown".
  stub_git_pushed
  stub_dispatch gh
  stub_dispatch kubectl
  stub_case kubectl 'get' 0 'registry.weyland.lab/scan-suite:git-2c73c898'
  printf '#!/usr/bin/env bash\ncase "$*" in\n  *"pipeline create"*) echo "41 pending"; exit 0 ;;\n  *) echo "Error: connection refused" >&2; exit 1 ;;\nesac\n' \
    > "$STUB_DIR/woodpecker-cli"
  chmod +x "$STUB_DIR/woodpecker-cli"
  SHIP_POLL_INTERVAL=1 SHIP_POLL_TIMEOUT=3 WOODPECKER_TOKEN=t SHIP_ENV_FILE=/nonexistent run bash "$SHIP"
  [ "$status" -ne 0 ]
  [[ "$output" == *"connection refused"* ]]
}

# --- TXN: one REAL transaction per shipped service (B140) ---------------------------------
#
# FR1.5 proves the right BYTES are on the node. SMOKE proves a readinessProbe measured something.
# NEITHER proves the service does its job — and on 2026-08-24 that gap was live, not theoretical:
#
#   feast-server was Argo-healthy, REST-answering, and green on the `/health` probe I had just
#   upgraded it to... while its ONLINE STORE WAS EMPTY. Valkey held 228 keys, all Langfuse's
#   `bull:*`, and zero Feast keys. Every entity key returned null — including invented ones.
#
# Likewise dagster-user-code's probe is `tcpSocket 4000`: it proves the gRPC server BOUND, not that
# its definitions LOADED. A code server that binds and fails to load passes SMOKE.
#
# The transactions run IN-CLUSTER via `kubectl exec`, deliberately. Every UI except feast.weyland.lab
# sits behind Keycloak forward-auth and 307s an unauthenticated curl; the alternative — carrying a
# credential into the ship path — would put Keycloak in the deploy critical path, which B140 says must
# be argued for explicitly rather than drifted into. In-cluster avoids the question entirely.

txn_stub_pod() {
  stub_dispatch kubectl
  stub_case kubectl 'get pod -l app=dagster-user-code' 0 'dagster-user-code-abc'
}

@test "TXN passes when both the Dagster and Feast transactions answer OK" {
  SHIP_IMAGES_LIB=1 source "$SHIP"
  printf '+ registry.weyland.lab/weyland-dagster-user-code:git-9a4996c6\n+ registry.weyland.lab/feast-server:git-9a4996c6\n' > "$STUB_DIR/d.diff"
  txn_stub_pod
  stub_case kubectl 'exec' 0 'TXN_OK'
  run txn_ok 'git-9a4996c6' "$STUB_DIR/d.diff"
  [ "$status" -eq 0 ]
}

@test "TXN FAILS when the Dagster code location did not load — the TCP-probe gap" {
  # The exact case SMOKE cannot see: the gRPC server is listening, definitions are broken.
  SHIP_IMAGES_LIB=1 source "$SHIP"
  printf '+ registry.weyland.lab/weyland-dagster-user-code:git-9a4996c6\n' > "$STUB_DIR/d.diff"
  txn_stub_pod
  stub_case kubectl 'exec' 0 'TXN_FAIL loadStatus=LOADING error=PythonError'
  run txn_ok 'git-9a4996c6' "$STUB_DIR/d.diff"
  [ "$status" -ne 0 ]
  [[ "$output" == *"weyland-dagster-user-code"* ]]
}

@test "TXN FAILS when Feast serves a NULL value — the empty-online-store case" {
  # Found live 2026-08-24. Note Feast answers `statuses: [PRESENT]` with `values: [null]` for a key
  # it never materialized, so the in-cluster check must assert the VALUE; a status-based check would
  # have been green against an empty store forever.
  SHIP_IMAGES_LIB=1 source "$SHIP"
  printf '+ registry.weyland.lab/feast-server:git-9a4996c6\n' > "$STUB_DIR/d.diff"
  txn_stub_pod
  stub_case kubectl 'exec' 0 'TXN_FAIL feast served null for a real entity key'
  run txn_ok 'git-9a4996c6' "$STUB_DIR/d.diff"
  [ "$status" -ne 0 ]
  [[ "$output" == *"feast-server"* ]]
}

@test "TXN NAMES an image it has no transaction for rather than silently passing it" {
  # Same discipline as smoke_ok: an unchecked image must never read as a verified one.
  SHIP_IMAGES_LIB=1 source "$SHIP"
  printf '+ registry.weyland.lab/scan-suite:git-9a4996c6\n+ registry.weyland.lab/feast-server:git-9a4996c6\n' > "$STUB_DIR/d.diff"
  txn_stub_pod
  stub_case kubectl 'exec' 0 'TXN_OK'
  run txn_ok 'git-9a4996c6' "$STUB_DIR/d.diff"
  [ "$status" -eq 0 ]
  [[ "$output" == *"scan-suite"* ]]
  [[ "$output" == *"no transaction"* ]]
}

@test "TXN fails closed when there is no pod to run the transaction from" {
  # Verifying nothing is not verifying successfully — the rule this loop has broken five times.
  SHIP_IMAGES_LIB=1 source "$SHIP"
  printf '+ registry.weyland.lab/feast-server:git-9a4996c6\n' > "$STUB_DIR/d.diff"
  stub_dispatch kubectl
  stub_case kubectl 'get pod' 0 ''
  run txn_ok 'git-9a4996c6' "$STUB_DIR/d.diff"
  [ "$status" -ne 0 ]
  [[ "$output" == *"no running"* ]]
}

@test "FR1.5 the pre-gate wait POLLS the same predicate the gate asserts" {
  # Run #29 (2026-08-24): the wait used `live_carries_tag` — "some pod somewhere has the tag" — which
  # is true the instant the FIRST new pod appears. It then handed a still-rolling cluster to a gate
  # requiring EVERY bumped image to be on the tag, and the run aborted on a rollout that was merely
  # in progress. A wait weaker than its gate is not a wait.
  #
  # Asserted behaviourally: with the cluster permanently mid-rollout, the loop must poll REPEATEDLY
  # before giving up, not check once. Checking once would satisfy a naive "it eventually failed" test.
  stub_git_pushed
  stub_dispatch woodpecker-cli
  stub_case woodpecker-cli 'pipeline create' 0 '42 pending'
  stub_case woodpecker-cli 'pipeline show' 0 '42 success'
  stub_dispatch gh
  stub_case gh 'pr list' 0 '13	ci/image-bump-9a4996c6	weyland-ci'
  stub_case gh 'isCrossRepository' 0 'false'
  stub_case gh 'pr view' 0 'weyland-ci'
  # ONE bumped image on purpose. all_bumped_images_live queries the cluster once PER IMAGE, so with a
  # two-image diff a SINGLE gate evaluation already makes two queries and a ">= 2 queries" assertion is
  # satisfied without any polling at all. With one image, one evaluation = one query, so reaching 2
  # requires actually looping. The two-image version of this test passed against the bug it was written
  # for -- caught by mutation-testing it, not by reading it.
  stub_case gh 'pr diff' 0 'diff --git a/k8s/x.yaml b/k8s/x.yaml
--- a/k8s/x.yaml
+++ b/k8s/x.yaml
-        image: registry.weyland.lab/weyland-flink:git-2c73c898
+        image: registry.weyland.lab/weyland-flink:git-9a4996c6'
  stub_dispatch argocd
  # Permanently mid-rollout: BOTH images stay on the old tag for the whole run.
  #
  # They must stay OLD, not partially-new: FR1.4 compares the newtag against the first bumped image,
  # so seeding scan-suite with the new tag makes the run abort at FR1.4 ("already deployed") and never
  # reach the wait this test is about. Cost me a debug cycle.
  # An UNRELATED workload already carries the new tag. That is what makes this test discriminate:
  # `live_carries_tag` greps EVERY pod for the tag, so tool-server alone satisfies it and the old wait
  # exits after a single check — while neither BUMPED image has arrived, so the gate still fails. With
  # both bumped images merely old, live_carries_tag is false too, the old wait also polls, and the
  # outcome is identical: the first version of this test passed against the bug it was written for.
  stub_dispatch kubectl
  stub_case kubectl 'status.phase=Running' 0 'registry.weyland.lab/weyland-tool-server:git-9a4996c6
registry.weyland.lab/scan-suite:git-2c73c898
registry.weyland.lab/weyland-flink:git-2c73c898'
  stub_case kubectl 'get cronjob' 0 ''
  stub_case kubectl 'get' 0 'registry.weyland.lab/weyland-tool-server:git-9a4996c6
registry.weyland.lab/scan-suite:git-2c73c898
registry.weyland.lab/weyland-flink:git-2c73c898'
  SHIP_POLL_INTERVAL=1 SHIP_ROLLOUT_TIMEOUT=3 run bash "$SHIP"
  [ "$status" -ne 0 ]
  [[ "$output" == *"FR1.5"* ]]
  [[ "$output" == *"weyland-flink"* ]]
  # THE ASSERTION, with the threshold DERIVED rather than guessed:
  #   with the bug  -> FR1.4 queries once + the FR1.5 gate queries once            = 2
  #   with the fix  -> those two PLUS one query per poll (interval 1, timeout 3)   >= 5
  # ">= 2" and even ">= 3" are met without any polling at all, which is why the first two versions of
  # THE ASSERTION, with the threshold DERIVED rather than guessed:
  #   with the bug  -> FR1.4 queries once + the gate queries once            = 2
  #   with the fix  -> those two, plus one query per poll (interval 1, 3s)   >= 6
  # ">= 2" is met without any polling at all, which is why the first two versions of this test passed
  # against the very bug they were written for. 4 sits cleanly between the two.
  [ "$(calls_to kubectl | grep -c 'status.phase=Running')" -ge 4 ]
}

@test "the loop fast-forwards local main after the merge — step 5 of the documented loop" {
  # Missing until 2026-08-24. `gh pr merge` advances origin/main, so without this the local clone is
  # exactly one commit behind after EVERY successful run and the operator's next push is rejected.
  # Happened twice before it was traced back here — the symptom surfaces in a human's git workflow,
  # several steps from the script that caused it.
  SHIP_IMAGES_LIB=1 source "$SHIP"
  stub_dispatch git
  stub_case git 'fetch' 0 ''
  stub_case git 'merge --ff-only' 0 ''
  run sync_local_main 42
  [ "$status" -eq 0 ]
  called_with git 'merge --ff-only origin/main'
  [[ "$output" == *"fast-forwarded"* ]]
}

@test "the fast-forward NEVER rebases or merges on the operator's behalf" {
  # A local commit makes ff impossible. The correct outcome is to SAY so and continue — this script
  # does not own the operator's history, and a verified rollout must not be failed over a git state.
  SHIP_IMAGES_LIB=1 source "$SHIP"
  stub_dispatch git
  stub_case git 'fetch' 0 ''
  stub_case git 'merge --ff-only' 1 ''
  run sync_local_main 42
  [ "$status" -eq 0 ]                      # friction, not a broken deploy
  [[ "$output" == *"could NOT fast-forward"* ]]
  not_called_with git 'rebase'
  not_called_with git 'merge origin'
}

@test "an unreachable origin is reported, not silently swallowed" {
  SHIP_IMAGES_LIB=1 source "$SHIP"
  stub_dispatch git
  stub_case git 'fetch' 1 ''
  run sync_local_main 42
  [ "$status" -eq 0 ]
  [[ "$output" == *"BEHIND"* ]]
  not_called_with git 'merge --ff-only'
}

@test "affected_apps returns 0 when NOTHING matches — an empty answer is not a failure" {
  # It ended `done | sort -u` with the loop body's last statement being `[ -n "$x" ] && printf`. With
  # no match that returns 1, and `set -o pipefail` propagates it past a successful sort — so the
  # caller's bare `apps="$(affected_apps …)"` killed the whole script under `set -e`, SILENTLY, right
  # after the merge: no sync, no FR1.5, no error. "No Argo app claims this manifest" is a legitimate
  # answer the caller already handles.
  SHIP_IMAGES_LIB=1 source "$SHIP"
  printf 'diff --git a/k8s/nope.yaml b/k8s/nope.yaml\n+ image: registry.weyland.lab/weyland-flink:git-9a4996c6\n' \
    > "$STUB_DIR/nomatch.diff"
  run affected_apps "$STUB_DIR/nomatch.diff"
  [ "$status" -eq 0 ]
  [ -z "$output" ]
}
