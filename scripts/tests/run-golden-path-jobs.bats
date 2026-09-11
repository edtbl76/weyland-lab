#!/usr/bin/env bats
#
# run-golden-path-jobs.sh — the B153 ephemeral exerciser. It makes decisions BEFORE it ever touches the
# cluster: resolve which paths to exercise, require each has a Dockerfile AND a non-empty .smoke command,
# and (for --dry-run) plan without building. Its exit contract is fail-closed: 2 = could not run (bad
# target / missing Dockerfile / missing .smoke / no paths at all), 1 = a smoke failed, 0 = all served.
#
# These cluster-free decision branches are tested here over a temp golden-paths tree (GOLDEN_PATH_DIR).
# The build + Job legs need a real buildkitd + kube and are proven by the `golden-path-smoke` CI step
# (pipeline #95, all 21 served), not mockable in bats. Fail-closed cases assert the REASON, not just a
# non-zero status — a bare `[ "$status" -eq 2 ]` also passes on exit 127 (command not found).

load helper

setup() {
  EX="$REPO_ROOT/scripts/run-golden-path-jobs.sh"
  GP="$(mktemp -d)"
  export GOLDEN_PATH_DIR="$GP"
}

teardown() {
  [ -n "${GP:-}" ] && [ -d "$GP" ] && rm -rf "$GP"
  unset GOLDEN_PATH_DIR
  return 0
}

# a valid golden path = a dir with a Dockerfile and a non-empty .smoke
mkpath() {
  mkdir -p "$GP/$1"
  printf 'FROM alpine:3.20\nCMD ["true"]\n' > "$GP/$1/Dockerfile"
  printf 'sh smoke.sh\n' > "$GP/$1/.smoke"
}

@test "--dry-run plans every path and touches no cluster (exit 0)" {
  mkpath demo/one
  mkpath demo/two
  run bash "$EX" --dry-run
  [ "$status" -eq 0 ]
  [[ "$output" == *"would build"* ]]
  [[ "$output" == *"demo/one"* ]]
  [[ "$output" == *"demo/two"* ]]
  # dry-run must NOT start a real build — no "== <path> ==" execution header.
  [[ "$output" != *"== demo/one =="* ]]
}

@test "discovery prunes build-artifact dirs — a dependency's Dockerfile is NOT a golden path (B104/#114)" {
  # A shared-workspace lane (test-cpp) leaves CMake FetchContent output at <path>/build/_deps/<lib>/Dockerfile.
  # The recursive Dockerfile discovery must NOT treat that as a golden path (no .smoke → the full run
  # failed exactly this way, pipeline #114 exit 2).
  mkpath cpp/httplib
  mkdir -p "$GP/cpp/httplib/build/_deps/httplib-src"
  printf 'FROM alpine:3.20\n' > "$GP/cpp/httplib/build/_deps/httplib-src/Dockerfile"   # a dep's own Dockerfile, no .smoke
  run bash "$EX" --dry-run
  [ "$status" -eq 0 ]                                   # NOT exit 2
  [[ "$output" == *"cpp/httplib"* ]]                    # the real path is planned
  [[ "$output" != *"build/_deps"* ]]                    # the artifact is not
}

@test "an explicit target with no Dockerfile fails closed with a reason (exit 2)" {
  mkpath demo/real
  run bash "$EX" demo/nope
  [ "$status" -eq 2 ]
  [[ "$output" == *"no golden path with a Dockerfile"* ]]
}

@test "a path with a Dockerfile but no .smoke fails closed with a reason (exit 2)" {
  mkdir -p "$GP/demo/nosmoke"
  printf 'FROM alpine:3.20\n' > "$GP/demo/nosmoke/Dockerfile"   # Dockerfile present, .smoke absent
  run bash "$EX" --dry-run demo/nosmoke
  [ "$status" -eq 2 ]
  [[ "$output" == *"no .smoke command"* ]]
}

@test "no golden paths at all fails closed with a reason (exit 2)" {
  run bash "$EX" --dry-run   # GOLDEN_PATH_DIR is an empty temp dir
  [ "$status" -eq 2 ]
  [[ "$output" == *"no golden paths found"* ]]
}
