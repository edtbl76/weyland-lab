#!/usr/bin/env bats
# scripts/check-dependabot-coverage.sh (B214, 2026-10-16) — every directory holding a requirements*.txt has a pip entry
# in .github/dependabot.yml. The config's own header says "an unlisted directory is an unwatched directory", yet 19 of
# 23 were unlisted (9 of them gained lockfiles in B213), so an advisory against those pins never reached a PR.
# Exit 0 = every directory watched · 1 = an unwatched one, named · 2 = the guard cannot check (no config, unparseable,
# no requirements directory found). Checking nothing is never a pass.

load helper

setup() {
  setup_stubs
  GUARD="$REPO_ROOT/scripts/check-dependabot-coverage.sh"
  T="$BATS_TEST_TMPDIR/repo"
  mkdir -p "$T/.github" "$T/services/a" "$T/services/b" "$T/golden-paths/python/flask"
  : > "$T/services/a/requirements.txt"
  : > "$T/services/b/requirements-extra.txt"
  : > "$T/golden-paths/python/flask/requirements.txt"
  export DEPENDABOT_ROOT="$T" DEPENDABOT_CONFIG="$T/.github/dependabot.yml"
}

teardown() { teardown_stubs; }

cfg() {  # cfg <dir>... — a config with one pip entry per dir
  { echo "version: 2"; echo "updates:"
    for d in "$@"; do printf '  - package-ecosystem: "pip"\n    directory: "%s"\n    open-pull-requests-limit: 0\n' "$d"; done
  } > "$DEPENDABOT_CONFIG"
}

@test "every requirements directory watched is exit 0, counted" {
  cfg /services/a /services/b
  run bash "$GUARD"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"OK — 2 requirements director"*"watched"* ]] || { echo "$output"; return 1; }
}

@test "an unwatched directory is exit 1, named" {
  cfg /services/a
  run bash "$GUARD"
  [ "$status" -eq 1 ] || { echo "$output"; return 1; }
  [[ "$output" == *"UNWATCHED: services/b"* ]] || { echo "$output"; return 1; }
}

@test "a docker-only entry does not watch a pip directory" {
  cfg /services/a
  printf '  - package-ecosystem: "docker"\n    directory: "/services/b"\n' >> "$DEPENDABOT_CONFIG"
  run bash "$GUARD"
  [ "$status" -eq 1 ] || { echo "$output"; return 1; }
  [[ "$output" == *"UNWATCHED: services/b"* ]]
}

@test "the plural 'directories' form counts" {
  printf 'version: 2\nupdates:\n  - package-ecosystem: "pip"\n    directories: ["/services/a", "/services/b"]\n' > "$DEPENDABOT_CONFIG"
  run bash "$GUARD"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}

@test "golden-paths templates are excluded, not unwatched" {
  cfg /services/a /services/b
  run bash "$GUARD"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" != *"golden-paths"*"UNWATCHED"* ]]
}

@test "a missing config is exit 2, never 'nothing to watch'" {
  rm -f "$DEPENDABOT_CONFIG"
  run bash "$GUARD"
  [ "$status" -eq 2 ] || { echo "$output"; return 1; }
  [[ "$output" == *"CANNOT CHECK"* ]]
}

@test "an unparseable config is exit 2" {
  printf 'updates: [unclosed\n' > "$DEPENDABOT_CONFIG"
  run bash "$GUARD"
  [ "$status" -eq 2 ] || { echo "$output"; return 1; }
  [[ "$output" == *"CANNOT CHECK"* ]]
}

@test "a tree with no requirements directory at all is exit 2" {
  rm -f "$T/services/a/requirements.txt" "$T/services/b/requirements-extra.txt"
  cfg /services/a
  run bash "$GUARD"
  [ "$status" -eq 2 ] || { echo "$output"; return 1; }
  [[ "$output" == *"CANNOT CHECK"* ]]
}

@test "the real repo: every requirements directory is watched" {
  unset DEPENDABOT_ROOT DEPENDABOT_CONFIG
  run bash "$GUARD"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
}
