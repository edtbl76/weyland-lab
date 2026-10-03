#!/usr/bin/env bats
# B177 — select-fixtures.sh: decide RUN_FIXTURES (1 = full fixture matrix, 0 = skip fixtures).
#
# The load-bearing invariant is FAIL-CLOSED: "0" (skip) is emitted ONLY on a git diff that succeeded and
# matched none of the manifest's fixture_trigger_paths. A missing/unparseable manifest, or any change
# under a trigger path, must print "1" — an absent/errored result must never read as "nothing changed"
# (project.md c14). The SELECT_CHANGED_FILES seam feeds a fixed changed-file list so the DECISION is
# tested without a git repo.

setup() {
  load helper
  setup_stubs
  GUARD="$REPO_ROOT/scripts/ci/select-fixtures.sh"
  # Real manifest by default; individual tests override CI_LANGS_FILE for the fail-closed cases.
  MANIFEST="$REPO_ROOT/ci-langs.yaml"
}

teardown() { teardown_stubs; }

@test "the selector exists and is executable-as-bash" {
  [ -f "$GUARD" ]
}

@test "a change under golden-paths/ runs the full matrix (1)" {
  SELECT_CHANGED_FILES=$'golden-paths/go/gin/main.go' CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$status" -eq 0 ]
  [ "$output" = "1" ]
}

@test "a change under tests/lang/ runs the full matrix (1)" {
  SELECT_CHANGED_FILES=$'tests/lang/shell/foo.bats' CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "1" ]
}

@test "a change to the lane runner runs the full matrix (1)" {
  SELECT_CHANGED_FILES=$'scripts/run-lang-tests.sh' CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "1" ]
}

@test "a change to .woodpecker.yml runs the full matrix (1)" {
  SELECT_CHANGED_FILES=$'.woodpecker.yml' CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "1" ]
}

@test "a change to the manifest itself runs the full matrix (1)" {
  SELECT_CHANGED_FILES=$'ci-langs.yaml' CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "1" ]
}

@test "changes ONLY to production/other code skip fixtures (0)" {
  SELECT_CHANGED_FILES=$'nodes/mother/lab/weyland-platform/services/weyland-dagster/foo.py\nscripts/check-linear-sync.sh\ndocs/backlog.md' \
    CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$status" -eq 0 ]
  [ "$output" = "0" ]
}

@test "an EMPTY diff fails closed to the full matrix (1) — ambiguous, not 'nothing changed'" {
  # Run after a push, HEAD == origin/main, so the diff is empty even if the push touched golden paths.
  # "0" (skip) must require POSITIVE evidence of a non-fixture-only change; empty is not that.
  SELECT_CHANGED_FILES=$'' CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "1" ]
}

@test "a mixed change (fixture + non-fixture) runs the full matrix (1)" {
  SELECT_CHANGED_FILES=$'docs/backlog.md\ngolden-paths/rust/axum/Cargo.toml' CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "1" ]
}

@test "an unreadable manifest fails closed to the full matrix (1)" {
  SELECT_CHANGED_FILES=$'docs/backlog.md' CI_LANGS_FILE="$STUB_DIR/nope.yaml" run bash "$GUARD"
  [ "$output" = "1" ]
}

@test "a manifest with no fixture_trigger_paths fails closed to the full matrix (1)" {
  printf 'production_lanes:\n  - test-python\n' > "$STUB_DIR/m.yaml"
  SELECT_CHANGED_FILES=$'docs/backlog.md' CI_LANGS_FILE="$STUB_DIR/m.yaml" run bash "$GUARD"
  [ "$output" = "1" ]
}

@test "a fixture path only counts as a real PREFIX (not a substring elsewhere)" {
  # 'x/golden-paths/go' must NOT match the 'golden-paths/' prefix — startswith, not contains.
  SELECT_CHANGED_FILES=$'vendor/x/golden-paths/go/main.go\ndocs/notes.md' CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "0" ]
}

# --- 2026-10-03: the golden-path smoke machinery is a trigger too --------------------------------------------------------
# A change to scripts/run-golden-path-jobs.sh (the run-scoped Job names, pipeline #242) selected LEAN (0), which skips
# golden-path-smoke — the one step that exercises that script. Its RBAC and the lib it sources have the same blind spot.

@test "a change to the golden-path smoke runner runs the full matrix (1)" {
  SELECT_CHANGED_FILES=$'scripts/run-golden-path-jobs.sh' CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "1" ]
}

@test "a change to the golden-paths k8s RBAC runs the full matrix (1)" {
  SELECT_CHANGED_FILES=$'nodes/mother/lab/weyland-platform/k8s/golden-paths/golden-paths-rbac.yaml' CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "1" ]
}

@test "a change to scripts/lib/common.sh (sourced by the lane runners) runs the full matrix (1)" {
  SELECT_CHANGED_FILES=$'scripts/lib/common.sh' CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "1" ]
}

# The audit that keeps the gap closed: every script a fixture-gated step runs — and every file that script sources —
# must be a trigger path, or a change to it gets a lean run that never exercises it.
@test "every script a lean-gated step runs (and what it sources) is in fixture_trigger_paths" {
  run python3 - "$REPO_ROOT" <<'PY'
import os, re, sys, yaml
root = sys.argv[1]
wp = yaml.safe_load(open(f"{root}/.woodpecker.yml"))
trig = yaml.safe_load(open(f"{root}/ci-langs.yaml"))["fixture_trigger_paths"]
gated = [s for s in wp["steps"] if 'RUN_FIXTURES != "0"' in str(s.get("when", ""))]
if not gated:
    sys.exit("no lean-gated steps found — the guard is checking nothing")
scripts = set()
for s in gated:
    for c in s.get("commands") or []:
        scripts.update(re.findall(r"(scripts/[\w./-]+\.sh)", str(c)))
seen, todo = set(), list(scripts)
while todo:                                   # follow `. "$(dirname "$0")/lib/x.sh"` style sources
    f = todo.pop()
    if f in seen or not os.path.exists(f"{root}/{f}"):
        continue
    seen.add(f)
    for m in re.findall(r'^\s*(?:\.|source)\s+"?\$\(dirname "\$(?:0|\{BASH_SOURCE\[0\]\})"\)/([\w./-]+)"?', open(f"{root}/{f}").read(), re.M):
        todo.append(os.path.normpath(os.path.join(os.path.dirname(f), m)))
missing = sorted(f for f in seen if not any(f.startswith(t) for t in trig))
print(f"{len(gated)} lean-gated steps, {len(seen)} scripts checked")
if missing:
    print("NOT a trigger path (a change here would skip the step that runs it):", missing); sys.exit(1)
PY
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"scripts checked"* ]] || { echo "$output"; return 1; }
}
