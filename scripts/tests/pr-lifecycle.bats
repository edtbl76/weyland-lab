#!/usr/bin/env bats
# B131 (resolution half) — check-pr-lifecycle.sh decision logic.
#
# The script's whole job is deciding what to do with what `gh` reports, so `gh` is stubbed (stub_dispatch:
# one binary, many hats — `pr list`, `api compare`, `api issues/comments`, `api pulls`) and every assertion is
# on the DECISION reached, never the canned JSON. The safety assertion the suite exists to hold: --apply NEVER
# merges, and it NEVER acts on a PR it could not classify (fail closed). A stray real merge/close would touch
# live PRs, so no test may let `gh` run for real.
#
# MULTI-REPO (B138 parity): the guard now defaults to the full pr-lane repo set (repos.yaml). Single-repo tests
# scope with `--repo edtbl76/test` so one stubbed repo drives them; multi-repo behaviour is exercised via
# PR_REPOS + per-repo `pr list --repo <r>` stub cases.

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
  # MERGEABLE candidates now have their diff read for downgrades (2026-09-25) — genuine upgrades here.
  stub_case gh 'pr diff 10 ' 0 "$(_diff_up_go)"
  stub_case gh 'pr diff 21 ' 0 "$(_diff_up_docker)"
  stub_case gh 'issues' 0 ''
  stub_case gh 'pulls'  0 ''
}

# Unified diffs, shaped like real `gh pr diff` output (observed on weyland-lab #63/#72/#80, 2026-09-25).
_diff_up_go() {
  printf '%s\n' 'diff --git a/svc-a/go.mod b/svc-a/go.mod' '--- a/svc-a/go.mod' '+++ b/svc-a/go.mod' '@@ -5 +5 @@' \
    '-	github.com/quic-go/quic-go v0.59.0' '+	github.com/quic-go/quic-go v0.59.1'
}
_diff_up_docker() {
  printf '%s\n' 'diff --git a/svc-d/Dockerfile b/svc-d/Dockerfile' '--- a/svc-d/Dockerfile' '+++ b/svc-d/Dockerfile' '@@ -1 +1 @@' \
    '-FROM img:1.0' '+FROM img:1.2'
}
_diff_up_pip() {
  printf '%s\n' 'diff --git a/svc/genre-trainer/requirements.txt b/svc/genre-trainer/requirements.txt' \
    '--- a/svc/genre-trainer/requirements.txt' '+++ b/svc/genre-trainer/requirements.txt' '@@ -1,2 +1,2 @@' \
    '-aiohttp==3.14.1' '+aiohttp==3.14.3'
}

@test "the guard exists" {
  [ -f "$GUARD" ]
}

@test "advisory: classifies each managed PR and prints the summary marker, exit 0" {
  _wire_mixed
  run bash "$GUARD" --repo edtbl76/test
  [ "$status" -eq 0 ]
  # #11 diverged -> STALE; #10 ahead+green -> MERGEABLE; #12 ci red -> NEEDS-HUMAN; #20 older -> SUPERSEDED.
  echo "$output" | grep -q '#11 \[STALE\]'
  echo "$output" | grep -q '#10 \[MERGEABLE\]'
  echo "$output" | grep -q '#12 \[NEEDS-HUMAN\]'
  echo "$output" | grep -q '#20 \[SUPERSEDED\]'
  echo "$output" | grep -q '#21 \[MERGEABLE\]'
  # per-repo line + grand total: 5 managed open (13 is a human feature branch, excluded).
  echo "$output" | grep -qE 'pr-lifecycle: edtbl76/test: 5 open \(1 stale, 1 superseded, 2 mergeable, 1 needs-human\)'
  echo "$output" | grep -qE 'pr-lifecycle-total: 1 repos, 5 open \(1 stale, 1 superseded, 2 mergeable, 1 needs-human\)'
  # the audit log emits a structured per-run summary line (the Loki record).
  echo "$output" | grep -qE 'pr-lifecycle-audit run=summary .* repos=1 open=5 stale=1 superseded=1 mergeable=2 needs_human=1 failed=0'
}

@test "advisory: a non-managed (human) branch is ignored" {
  _wire_mixed
  run bash "$GUARD" --repo edtbl76/test
  [ "$status" -eq 0 ]
  not_called_with gh 'compare/main...feature/my-thing'
  not_called_with gh '#13'
}

@test "advisory NEVER mutates — no comment, no close, no merge" {
  _wire_mixed
  run bash "$GUARD" --repo edtbl76/test
  [ "$status" -eq 0 ]
  not_called_with gh '-X POST'
  not_called_with gh '-X PATCH'
  not_called_with gh 'merge'
}

@test "--apply: recreates STALE and closes SUPERSEDED, but NEVER merges" {
  _wire_mixed
  run bash "$GUARD" --apply --repo edtbl76/test
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
  # the audit log records each applied action with its result (the Loki resolution history).
  echo "$output" | grep -qE 'repo=edtbl76/test pr=11 verdict=STALE action=recreate result=ok'
  echo "$output" | grep -qE 'repo=edtbl76/test pr=20 verdict=SUPERSEDED action=close by=21 result=ok'
}

@test "fail closed: gh pr list transport/auth failure -> exit 2, not a clean sweep" {
  stub_dispatch gh
  stub_case gh 'pr list' 1 'HTTP 401: Bad credentials'
  run bash "$GUARD" --repo edtbl76/test
  [ "$status" -eq 2 ]
  echo "$output" | grep -q 'could not list PRs'
}

@test "fail closed: an unresolvable compare is exit 2, never treated as current" {
  stub_dispatch gh
  stub_case gh 'pr list' 0 '[{"number":11,"title":"x","headRefName":"dependabot/pip/svc-b/aiohttp-bbbbbbbb","createdAt":"2026-09-02T00:00:00Z","isDraft":false,"statusCheckRollup":[{"conclusion":"SUCCESS"}]}]'
  # compare unmatched -> stub_dispatch exits 0 with EMPTY output -> compare_status must read that as ERROR.
  run bash "$GUARD" --repo edtbl76/test
  [ "$status" -eq 2 ]
  echo "$output" | grep -q 'could not compare'
}

@test "no open managed PRs -> clean summary, exit 0" {
  stub_dispatch gh
  stub_case gh 'pr list' 0 '[{"number":13,"title":"human","headRefName":"feature/x","createdAt":"2026-09-04T00:00:00Z","isDraft":false,"statusCheckRollup":[]}]'
  run bash "$GUARD" --repo edtbl76/test
  [ "$status" -eq 0 ]
  echo "$output" | grep -qE 'pr-lifecycle-total: 1 repos, 0 open \(0 stale, 0 superseded, 0 mergeable, 0 needs-human\)'
}

@test "ci/image-bump: survivor is MERGEABLE (ship loop), older is SUPERSEDED, and compare is NOT called" {
  stub_dispatch gh
  stub_case gh 'pr list' 0 '[
    {"number":40,"title":"ci: image bump (old)","headRefName":"ci/image-bump-git-aaaa1111","createdAt":"2026-09-01T00:00:00Z","isDraft":false,"statusCheckRollup":[{"conclusion":"SUCCESS"}]},
    {"number":41,"title":"ci: image bump (new)","headRefName":"ci/image-bump-git-bbbb2222","createdAt":"2026-09-02T00:00:00Z","isDraft":false,"statusCheckRollup":[{"conclusion":"SUCCESS"}]}
  ]'
  run bash "$GUARD" --repo edtbl76/test
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
  run bash "$GUARD" --apply --repo edtbl76/test
  [ "$status" -eq 0 ]
  called_with gh 'pulls/40'
  not_called_with gh '@dependabot recreate'
  not_called_with gh 'merge'
}

@test "multi-repo: loops PR_REPOS and aggregates the grand total across repos" {
  stub_dispatch gh
  # one stale dependabot PR, returned for BOTH repos (generic 'pr list' + a diverged compare).
  stub_case gh 'pr list' 0 '[{"number":11,"title":"x","headRefName":"dependabot/pip/svc-b/aiohttp-bbbbbbbb","createdAt":"2026-09-02T00:00:00Z","isDraft":false,"statusCheckRollup":[{"conclusion":"SUCCESS"}]}]'
  stub_case gh 'compare/main...dependabot/pip/svc-b/aiohttp-bbbbbbbb' 0 'diverged'
  run env PR_REPOS="edtbl76/r1 edtbl76/r2" bash "$GUARD"
  [ "$status" -eq 0 ]
  echo "$output" | grep -q 'Open managed PRs in edtbl76/r1'
  echo "$output" | grep -q 'Open managed PRs in edtbl76/r2'
  # grand total sums 1 stale per repo -> 2 repos, 2 open, 2 stale.
  echo "$output" | grep -qE 'pr-lifecycle-total: 2 repos, 2 open \(2 stale, 0 superseded, 0 mergeable, 0 needs-human\)'
  echo "$output" | grep -qE 'pr-lifecycle-audit run=summary .* repos=2 open=2 stale=2 .* failed=0'
}

@test "multi-repo fail-closed: one unreachable repo exits 2 but the others are still reconciled" {
  stub_dispatch gh
  # good repo: a clean image-bump survivor (no compare needed) -> reconciles fine.
  stub_case gh 'pr list --repo edtbl76/good' 0 '[{"number":41,"title":"ci: image bump","headRefName":"ci/image-bump-git-bbbb2222","createdAt":"2026-09-02T00:00:00Z","isDraft":false,"statusCheckRollup":[{"conclusion":"SUCCESS"}]}]'
  # bad repo: pr list transport failure.
  stub_case gh 'pr list --repo edtbl76/bad' 1 'HTTP 500: upstream'
  run env PR_REPOS="edtbl76/good edtbl76/bad" bash "$GUARD"
  # a single unreachable repo must force a non-zero exit — never a silent shrink of the watch set.
  [ "$status" -eq 2 ]
  # but the good repo was STILL fully reconciled (isolation via subshell).
  echo "$output" | grep -q 'Open managed PRs in edtbl76/good'
  echo "$output" | grep -q '#41 \[MERGEABLE\]'
  # and the failure is named explicitly, fail closed.
  echo "$output" | grep -qE 'could not reconcile.*edtbl76/bad'
}

# --- STALE = main changed what the PR touches, not merely "behind" (2026-09-25) ------------------------------
# `behind` alone made STALE unreachable to escape on a busy trunk: main takes ~16 commits/day, so every nightly
# `@dependabot recreate` was behind again by morning and weyland-lab #63/#72/#80 looped on recreate for days
# with ZERO overlap. The regression the rule exists for (2026-09-21, #63 downgrading cryptography) needs main
# to have changed the PR's OWN dependency files. So: STALE iff main changed a file in a DIRECTORY the PR touches
# since the merge base. Anything unprovable (lookup failed / empty / truncated) stays STALE — over-flagging costs
# one harmless recreate; under-flagging merges a downgrade. Stub shapes observed on the live API 2026-09-25:
# `pulls/<n>/files` -> one filename per line; `compare/<branch>...main` -> "<commits> <files>" then filenames.

_one_dependabot_pr() {
  local ci="${1:-SUCCESS}"
  printf '[{"number":30,"title":"Bump aiohttp","headRefName":"dependabot/pip/svc/genre-trainer/aiohttp-ffffffff","createdAt":"2026-09-01T00:00:00Z","isDraft":false,"statusCheckRollup":[{"conclusion":"%s"}]}]' "$ci"
}

_wire_behind() {   # $1 = CI conclusion, then the main-side answer (exit, stdout)
  stub_dispatch gh
  stub_case gh 'pr list' 0 "$(_one_dependabot_pr "$1")"
  stub_case gh 'compare/main...dependabot/pip/svc/genre-trainer/aiohttp-ffffffff' 0 'diverged'
  stub_case gh 'pulls/30/files' 0 "$(printf 'svc/genre-trainer/requirements.in\nsvc/genre-trainer/requirements.txt')"
  stub_case gh 'pr diff 30 ' 0 "$(_diff_up_pip)"
}

@test "behind, but main changed NOTHING the PR touches + CI green -> MERGEABLE, no recreate" {
  _wire_behind SUCCESS
  stub_case gh 'compare/dependabot/pip/svc/genre-trainer/aiohttp-ffffffff...main' 0 "$(printf '16 3\n.woodpecker.yml\ndocs/backlog.md\nsvc/weyland-dagster/requirements.txt')"
  run bash "$GUARD" --repo edtbl76/test --apply
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '#30 \[MERGEABLE\]'
  not_called_with gh 'issues/30/comments'
}

@test "the #63 replay: main changed a dependency file in the PR's directory -> STALE + recreate" {
  _wire_behind SUCCESS
  # main hand-remediated cryptography in the SAME requirements file the stale PR carries.
  stub_case gh 'compare/dependabot/pip/svc/genre-trainer/aiohttp-ffffffff...main' 0 "$(printf '4 2\nsvc/genre-trainer/requirements.txt\ndocs/backlog.md')"
  run bash "$GUARD" --repo edtbl76/test
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '#30 \[STALE\]'
}

@test "overlap is by DIRECTORY: main edited requirements.in, PR touches only requirements.txt -> STALE" {
  stub_dispatch gh
  stub_case gh 'pr list' 0 "$(_one_dependabot_pr SUCCESS)"
  stub_case gh 'compare/main...dependabot/pip/svc/genre-trainer/aiohttp-ffffffff' 0 'behind'
  stub_case gh 'pulls/30/files' 0 'svc/genre-trainer/requirements.txt'
  stub_case gh 'compare/dependabot/pip/svc/genre-trainer/aiohttp-ffffffff...main' 0 "$(printf '1 1\nsvc/genre-trainer/requirements.in')"
  run bash "$GUARD" --repo edtbl76/test
  echo "$output" | grep -q '#30 \[STALE\]'
}

@test "unprovable: the main-side lookup returns nothing -> STALE, never MERGEABLE" {
  _wire_behind SUCCESS
  run bash "$GUARD" --repo edtbl76/test
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '#30 \[STALE\]'
}

@test "unprovable: the main-side compare is TRUNCATED (300 files) -> STALE" {
  _wire_behind SUCCESS
  stub_case gh 'compare/dependabot/pip/svc/genre-trainer/aiohttp-ffffffff...main' 0 "$(printf '40 300\ndocs/backlog.md')"
  run bash "$GUARD" --repo edtbl76/test
  echo "$output" | grep -q '#30 \[STALE\]'
}

@test "unprovable: the PR's own file list is empty -> STALE" {
  stub_dispatch gh
  stub_case gh 'pr list' 0 "$(_one_dependabot_pr SUCCESS)"
  stub_case gh 'compare/main...dependabot/pip/svc/genre-trainer/aiohttp-ffffffff' 0 'diverged'
  stub_case gh 'compare/dependabot/pip/svc/genre-trainer/aiohttp-ffffffff...main' 0 "$(printf '2 1\ndocs/backlog.md')"
  run bash "$GUARD" --repo edtbl76/test
  echo "$output" | grep -q '#30 \[STALE\]'
}

@test "behind, no overlap, but CI red -> NEEDS-HUMAN (not STALE, not MERGEABLE)" {
  _wire_behind FAILURE
  stub_case gh 'compare/dependabot/pip/svc/genre-trainer/aiohttp-ffffffff...main' 0 "$(printf '16 1\ndocs/backlog.md')"
  run bash "$GUARD" --repo edtbl76/test
  echo "$output" | grep -q '#30 \[NEEDS-HUMAN\]'
}

# --- REGRESSIVE: a "bump" whose diff DOWNGRADES a pin is never MERGEABLE (2026-09-25) --------------------------
# weyland-lab #63 was titled "Bump aiohttp 3.14.1 -> 3.14.3" and downgraded cryptography 50.0.0 -> 48.0.1 and mlflow
# 3.15.1 -> 3.14.0 (re-opening 4 CVEs); #72 ("Bump soupsieve") downgraded dagster-dbt 0.29.14 -> 0.10.9. Both came
# from dependabot recompiling a stale requirements.in. Only a Sourcery check stopped #63 — with CI green the reconciler
# called such a PR MERGEABLE. The title is not evidence: every otherwise-mergeable dependabot PR has its DIFF read, and
# any pinned version that goes DOWN makes it NEEDS-HUMAN. An unreadable diff is NEEDS-HUMAN too (unproven != safe).

_wire_one_current() {   # $1 = the PR's diff (a current, CI-green dependabot PR #50)
  stub_dispatch gh
  stub_case gh 'pr list' 0 '[{"number":50,"title":"Bump aiohttp from 3.14.1 to 3.14.3","headRefName":"dependabot/pip/svc/genre-trainer/security-and-patches-abcdef12","createdAt":"2026-09-01T00:00:00Z","isDraft":false,"statusCheckRollup":[{"conclusion":"SUCCESS"}]}]'
  stub_case gh 'compare/main...dependabot/pip/svc/genre-trainer/security-and-patches-abcdef12' 0 'ahead'
  [ -n "$1" ] && stub_case gh 'pr diff 50 ' 0 "$1"
  stub_case gh 'issues' 0 ''
  stub_case gh 'pulls'  0 ''
}

@test "REGRESSIVE: the #63 case — a pip 'bump' that downgrades cryptography + mlflow -> NEEDS-HUMAN, named" {
  _wire_one_current "$(printf '%s\n' 'diff --git a/svc/genre-trainer/requirements.txt b/svc/genre-trainer/requirements.txt' \
    '--- a/svc/genre-trainer/requirements.txt' '+++ b/svc/genre-trainer/requirements.txt' '@@ -1,5 +1,5 @@' \
    '-aiohttp==3.14.1' '+aiohttp==3.14.3' '-cryptography==50.0.0' '+cryptography==48.0.1' \
    '-mlflow==3.15.1' '+mlflow==3.14.0')"
  run bash "$GUARD" --repo edtbl76/test
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '#50 \[NEEDS-HUMAN\]'
  echo "$output" | grep -q 'REGRESSIVE'
  echo "$output" | grep -q 'cryptography 50.0.0->48.0.1'
  echo "$output" | grep -q 'mlflow 3.15.1->3.14.0'
}

@test "REGRESSIVE: the #72 case — an ancient version on a renamed-case line is still caught" {
  _wire_one_current "$(printf '%s\n' 'diff --git a/r.txt b/r.txt' '--- a/r.txt' '+++ b/r.txt' '@@ -1,3 +1,3 @@' \
    '-dagster-dbt==0.29.14' '+dagster-dbt==0.10.9' '-soupsieve==2.6     # pinned' '+soupsieve==2.9')"
  run bash "$GUARD" --repo edtbl76/test
  echo "$output" | grep -q '#50 \[NEEDS-HUMAN\]'
  echo "$output" | grep -q 'dagster-dbt 0.29.14->0.10.9'
}

@test "REGRESSIVE: a go.sum module downgrade is caught" {
  _wire_one_current "$(printf '%s\n' 'diff --git a/go.sum b/go.sum' '--- a/go.sum' '+++ b/go.sum' '@@ -1,2 +1,2 @@' \
    '-golang.org/x/net v0.30.0 h1:abc=' '+golang.org/x/net v0.28.0 h1:def=')"
  run bash "$GUARD" --repo edtbl76/test
  echo "$output" | grep -q '#50 \[NEEDS-HUMAN\]'
  echo "$output" | grep -q 'golang.org/x/net 0.30.0->0.28.0'
}

@test "REGRESSIVE: a yarn (berry) lockfile downgrade is caught" {
  _wire_one_current "$(printf '%s\n' 'diff --git a/yarn.lock b/yarn.lock' '--- a/yarn.lock' '+++ b/yarn.lock' '@@ -1,4 +1,4 @@' \
    ' "nanoid@npm:^3.3.16":' '-  version: 3.3.19' '+  version: 3.3.16' '   linkType: hard')"
  run bash "$GUARD" --repo edtbl76/test
  echo "$output" | grep -q '#50 \[NEEDS-HUMAN\]'
  echo "$output" | grep -q 'nanoid 3.3.19->3.3.16'
}

@test "REGRESSIVE: an npm package-lock downgrade is caught" {
  _wire_one_current "$(printf '%s\n' 'diff --git a/package-lock.json b/package-lock.json' '--- a/package-lock.json' '+++ b/package-lock.json' '@@ -1,4 +1,4 @@' \
    '     "node_modules/next": {' '-      "version": "16.3.3",' '+      "version": "16.2.11",')"
  run bash "$GUARD" --repo edtbl76/test
  echo "$output" | grep -q '#50 \[NEEDS-HUMAN\]'
  echo "$output" | grep -q 'next 16.3.3->16.2.11'
}

@test "a genuine upgrade stays MERGEABLE (the check does not over-fire)" {
  _wire_one_current "$(_diff_up_pip)"
  run bash "$GUARD" --repo edtbl76/test
  echo "$output" | grep -q '#50 \[MERGEABLE\]'
}

@test "an UNREADABLE diff is NEEDS-HUMAN — unproven is not safe" {
  _wire_one_current ""
  run bash "$GUARD" --repo edtbl76/test
  [ "$status" -eq 0 ]
  echo "$output" | grep -q '#50 \[NEEDS-HUMAN\]'
  echo "$output" | grep -q 'could not read the diff'
}

@test "--apply takes NO action on a REGRESSIVE PR (no comment, no close, no merge)" {
  _wire_one_current "$(printf '%s\n' 'diff --git a/r.txt b/r.txt' '--- a/r.txt' '+++ b/r.txt' '@@ -1 +1 @@' '-cryptography==50.0.0' '+cryptography==48.0.1')"
  run bash "$GUARD" --repo edtbl76/test --apply
  echo "$output" | grep -q '#50 \[NEEDS-HUMAN\]'
  not_called_with gh 'issues/50/comments'
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
