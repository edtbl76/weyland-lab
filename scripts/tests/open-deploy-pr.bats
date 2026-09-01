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

# --- FR3.4 the branch already on origin --------------------------------------------------
#
# THE DEFECT: the 422 handling above is thorough, and the step never reached it. It died two steps
# earlier, on the PUSH.
#
# `BRANCH` is derived from the sha (`ci/image-bump-<sha>`), so any re-run of the same commit finds
# its own branch already on origin. `git push HEAD:$BRANCH` is then a non-fast-forward — the commit
# objects differ even when the file content is identical, because the tree is re-committed with a
# new timestamp — so git rejects it, `set -eu` kills the step, and `2>/dev/null` discards the reason.
#
# Observed live: Woodpecker #26 (manual) pushed ci/image-bump-dab283e9 and opened PR #36. The
# nightly cron #27 rebuilt the SAME sha six hours later, produced commit 058b4bd against origin's
# 89fa700, and failed. It will fail every single night until PR #36 merges. The log ends at
# "5 files changed" with no error at all.

@test "FR3.4 succeeds when the branch is already on origin with identical content" {
  # THE REGRESSION. Must not push, must not fail — go straight on to the PR step.
  stub_dispatch git
  stub_case git 'ls-remote'   0 'aaaaaaa refs/heads/ci/image-bump-9a4996c6'
  stub_case git 'fetch'       0 ''
  # Same tree hash on both sides = the work is already published.
  stub_case git 'rev-parse'   0 'deadbeefdeadbeefdeadbeefdeadbeefdeadbeef'
  stub_dispatch curl
  stub_case curl '-X POST' 0 '{"message":"Validation Failed"}
422'
  stub_case curl 'pulls?head=' 0 '[{"number":36}]
200'
  run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  # It must NOT have attempted the doomed push.
  not_called_with git 'push'
  [[ "$output" == *"already"* ]]
}

@test "FR3.4 surfaces the push failure instead of discarding it" {
  # `2>/dev/null` on the push is why #27's log ends mid-step with no error. Whatever git says must
  # reach the operator.
  stub_dispatch git
  stub_case git 'ls-remote' 1 ''
  printf '#!/usr/bin/env bash\nprintf "git %%s\\n" "$*" >> "%s"\ncase "$*" in\n  *ls-remote*) exit 1 ;;\n  *push*) echo "! [rejected] ci/image-bump-9a4996c6 (non-fast-forward)" >&2; exit 1 ;;\nesac\nexit 0\n' \
    "$STUB_LOG" > "$STUB_DIR/git"
  chmod +x "$STUB_DIR/git"
  stub curl 0 '{"html_url":"x"}
201'
  run bash "$SCRIPT"
  [ "$status" -ne 0 ]
  [[ "$output" == *"non-fast-forward"* ]]
}

@test "FR3.4 a brand-new branch still pushes normally" {
  # The control. Without it, a fix that never pushes anything would pass the test above.
  stub_dispatch git
  stub_case git 'ls-remote' 1 ''
  stub_dispatch curl
  stub_case curl '-X POST' 0 '{"html_url":"https://github.com/edtbl76/weyland-lab/pull/40"}
201'
  run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  called_with git 'push'
  [[ "$output" == *"pull/40"* ]]
}

@test "FR2.1 the bump commit stages ONLY the manifests it changed — never git commit -a" {
  # 2026-09-01: the step committed with `git commit -am`, which sweeps EVERY dirty tracked file. A bump
  # whose pipeline had just run the python lane carried `.coverage` (a tracked, regenerated binary) and a
  # coverage-baseline bump into PR #61 alongside the tag lines — non-tags-only — and ship-images.sh
  # aborted at FR2.1. The fix stages exactly the bumped manifests, so anything else the pipeline dirtied
  # stays out of the commit. Asserted on the git invocations: the manifest is `add`ed, and the commit
  # carries NO `-a`.
  export PLATFORM="$WORK"
  mkdir -p "$WORK/k8s"
  printf 'spec:\n  image: registry.weyland.lab/scan-suite:git-old\n' >"$WORK/k8s/x.yaml"
  printf 'scan-suite\tgit-9a4996c6\tk8s/x.yaml\n' >"$WORK/bumps"
  stub_dispatch curl
  stub_case curl '-X POST' 0 '{"html_url":"https://github.com/edtbl76/weyland-lab/pull/41"}
201'
  run bash "$SCRIPT"
  [ "$status" -eq 0 ]
  called_with git 'add'                         # the manifest is staged explicitly
  called_with git "$WORK/k8s/x.yaml"            # and it is THIS manifest
  not_called_with git 'commit -am'              # the sweep-all form is gone
  not_called_with git 'commit -a '              # …in any spelling
  called_with git 'commit -m'                   # committed, just scoped
}
