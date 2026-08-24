#!/usr/bin/env bats
# Change detection for scripts/ci/detect-changes.sh — the script that decides which images rebuild.
#
# WHY THIS SUITE EXISTS (2026-08-24): `bash scripts/ship-images.sh` was run from a subdirectory
# (nodes/.../tofu/port) while a real dbt-core/sqlparse bump sat committed on main. It reported
#
#     ✓ nothing to ship — no image build context changed since its deployed tag.
#
# and exited 0. Three images had in fact changed. detect-changes.sh resolved BOTH of its inputs
# relatively (TSV="scripts/ci/images.tsv", PLATFORM="nodes/..."), so from any other directory the
# TSV was simply not there — and the failure was invisible because
#
#     grep -v '#' "$TSV" | grep -v '' | while read ...; do ... done
#
# takes its exit status from the LAST command in the pipeline. A `while` loop over empty input
# succeeds, so grep's "No such file or directory" (exit 2, stderr) became exit 0 + an empty plan,
# which every caller reads as "a quiet day".
#
# That is the same class already recorded three times in this effort (woodpecker-cli --output json
# silently ignored, curl -sf collapsing non-2xx to 0, promtool exiting 0 while printing FAILED) and
# in aidlc project.md: an absent or failed result must NEVER stand for success.
#
# git is STUBBED here rather than real. These tests are about path resolution and fail-closed
# behaviour, not about git's diff semantics, and the CI harness mounts the repo READ-ONLY into
# bats/bats:latest — which has no git. A fake repo tree in a temp dir plus a dispatching git stub
# exercises the real decision without either constraint.

setup() {
  load helper
  setup_stubs
  DETECT="$REPO_ROOT/scripts/ci/detect-changes.sh"

  # A minimal but REAL repo shape: the TSV the script reads, and the manifest it reads the currently
  # deployed tag out of.
  FAKE="$(mktemp -d)"
  export FAKE
  mkdir -p "$FAKE/scripts/ci" "$FAKE/nodes/mother/lab/weyland-platform/k8s/code-quality"
  printf '# comment row, must be skipped\n' > "$FAKE/scripts/ci/images.tsv"
  printf 'scan-suite\tservices/scan-suite\tk8s/code-quality/scan-suite.yaml\n' \
    >> "$FAKE/scripts/ci/images.tsv"
  printf 'image: registry.weyland.lab/scan-suite:git-2c73c898\n' \
    > "$FAKE/nodes/mother/lab/weyland-platform/k8s/code-quality/scan-suite.yaml"

  PLAN_FILE="$FAKE/plan.out"
  export PLAN_FILE

  # git answers, in first-match-wins order. `diff --quiet` exits 1 = "there is a difference", which
  # is what makes scan-suite a BUILD in the happy path.
  stub_dispatch git
  stub_case git 'rev-parse --show-toplevel'      0 "$FAKE"
  stub_case git 'rev-parse --short=8'            0 '9a4996c6'
  stub_case git 'rev-parse --is-shallow'         0 'false'
  stub_case git 'cat-file'                       0 ''
  stub_case git 'diff --quiet'                   1 ''
}

teardown() {
  [ -n "${FAKE:-}" ] && [ -d "$FAKE" ] && rm -rf "$FAKE"
  teardown_stubs
}

# --- cwd independence -----------------------------------------------------------------

@test "detects a changed context when run from the repo root" {
  # The control for the test below: same inputs, cwd = repo root. If this ever fails the next test
  # proves nothing, because a green "works from elsewhere" would just mean the fixture is broken.
  cd "$FAKE"
  PLAN="$PLAN_FILE" run sh "$DETECT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"scan-suite"*"BUILD"* ]]
  grep -q '^scan-suite' "$PLAN_FILE"
}

@test "detects the SAME changed context when run from a subdirectory" {
  # THE REGRESSION. Before the fix this printed "0 image(s) to build" and exited 0 from anywhere
  # that was not the repo root — a green answer with no work behind it.
  mkdir -p "$FAKE/nodes/mother/lab/weyland-platform/tofu/port"
  cd "$FAKE/nodes/mother/lab/weyland-platform/tofu/port"
  PLAN="$PLAN_FILE" run sh "$DETECT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"scan-suite"*"BUILD"* ]]
  grep -q '^scan-suite' "$PLAN_FILE"
}

@test "detects the SAME changed context when run from outside the repo entirely" {
  cd /tmp
  PLAN="$PLAN_FILE" run sh "$DETECT"
  [ "$status" -eq 0 ]
  grep -q '^scan-suite' "$PLAN_FILE"
}

# --- fail closed ----------------------------------------------------------------------

@test "fails closed, naming the manifest, when the image TSV is unreadable" {
  # Asserting only `status -ne 0` would pass on exit 127 (command not found) — the exact hole found
  # on 2026-08-23 in the SMOKE gate's own test. Assert the REASON.
  rm -f "$FAKE/scripts/ci/images.tsv"
  cd "$FAKE"
  PLAN="$PLAN_FILE" run sh "$DETECT"
  [ "$status" -ne 0 ]
  [[ "$output" == *"images.tsv"* ]]
  [[ "$output" == *"refusing"* ]]
  # And it must NOT have left a plan that a caller would read as "nothing to build".
  [ ! -s "$PLAN_FILE" ]
}

@test "fails closed when the TSV exists but carries no image rows" {
  # Verifying nothing is not verifying successfully. A TSV emptied by a bad edit or a truncated
  # checkout produces zero rows, an empty plan, and — before the fix — a confident exit 0.
  printf '# every row commented out\n#scan-suite\tservices/scan-suite\tk8s/x.yaml\n' \
    > "$FAKE/scripts/ci/images.tsv"
  cd "$FAKE"
  PLAN="$PLAN_FILE" run sh "$DETECT"
  [ "$status" -ne 0 ]
  [[ "$output" == *"no image rows"* ]]
}

@test "fails closed, naming git, when not inside a git work tree" {
  # `git rev-parse --show-toplevel` is the anchor for every path. If it cannot answer, nothing
  # downstream can be trusted, so the script must stop rather than fall back to relative paths.
  stub_dispatch git
  stub_case git 'rev-parse --show-toplevel' 128 ''
  cd /tmp
  PLAN="$PLAN_FILE" run sh "$DETECT"
  [ "$status" -ne 0 ]
  [[ "$output" == *"repo root"* ]]
}

# --- the plan is still what the build step consumes ------------------------------------

@test "an unchanged context is skipped rather than built" {
  # diff --quiet exits 0 = no difference. Guards against a fix that makes everything build.
  stub_dispatch git
  stub_case git 'rev-parse --show-toplevel' 0 "$FAKE"
  stub_case git 'rev-parse --short=8'       0 '9a4996c6'
  stub_case git 'rev-parse --is-shallow'    0 'false'
  stub_case git 'cat-file'                  0 ''
  stub_case git 'diff --quiet'              0 ''
  cd "$FAKE"
  PLAN="$PLAN_FILE" run sh "$DETECT"
  [ "$status" -eq 0 ]
  [[ "$output" == *"unchanged"* ]]
  [ ! -s "$PLAN_FILE" ]
}
