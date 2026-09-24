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

@test "an empty (successful) diff skips fixtures (0) — nothing changed" {
  SELECT_CHANGED_FILES=$'' CI_LANGS_FILE="$MANIFEST" run bash "$GUARD"
  [ "$output" = "0" ]
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
