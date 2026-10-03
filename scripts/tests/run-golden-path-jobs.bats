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

@test "discovery prunes SwiftPM .build/checkouts — a dep's Dockerfile is NOT a golden path (B164/#127)" {
  # test-swift builds golden-paths/swift/vapor-app, and SwiftPM clones deps into .build/checkouts/<dep>;
  # swift-nio-ssl ships its OWN docker/Dockerfile there. The shared workspace carries it into this step,
  # and the full run failed exactly this way (#127 exit 2). The dot-dir `.build` is NOT matched by the
  # `-name build` prune term, so it needs its own — this guards that it is pruned.
  mkpath swift/vapor-app
  mkdir -p "$GP/swift/vapor-app/.build/checkouts/swift-nio-ssl/docker"
  printf 'FROM alpine:3.20\n' > "$GP/swift/vapor-app/.build/checkouts/swift-nio-ssl/docker/Dockerfile"
  run bash "$EX" --dry-run
  [ "$status" -eq 0 ]                                   # NOT exit 2
  [[ "$output" == *"swift/vapor-app"* ]]                # the real path is planned
  [[ "$output" != *".build/checkouts"* ]]               # the dep's Dockerfile is not
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

# --- 2026-10-03: run-scoped Job names ---------------------------------------------------------------------------------
# Pipelines #238 (manual) and #239 (nightly-images) ran golden-path-smoke at the same time (06:01-06:31 UTC). Both used
# the Job name gp-<lang>-<framework> and each DELETES that Job before applying its own, so they killed each other's
# smoke Jobs mid-run: 13 + 12 "SMOKE FAILED" with no log. The Job name now carries the run: p<CI_PIPELINE_NUMBER> in CI,
# h<epoch> by hand, or GOLDEN_PATH_RUN_ID.

@test "in CI the Job name carries the pipeline number" {
  mkpath demo/one
  CI_PIPELINE_NUMBER=240 run bash "$EX" --dry-run
  [ "$status" -eq 0 ]
  [[ "$output" == *"run Job gp-demo-one-p240/"* ]] || { echo "$output"; return 1; }
}

@test "two overlapping pipelines get DIFFERENT Job names for the same path (the #238/#239 collision)" {
  mkpath demo/one
  CI_PIPELINE_NUMBER=238 run bash "$EX" --dry-run
  a="$(grep -o 'run Job [^/]*' <<<"$output")"
  CI_PIPELINE_NUMBER=239 run bash "$EX" --dry-run
  b="$(grep -o 'run Job [^/]*' <<<"$output")"
  [ -n "$a" ] && [ -n "$b" ] && [ "$a" != "$b" ] || { echo "a=$a b=$b"; return 1; }
}

@test "by hand (no CI number) the Job name still carries a run suffix" {
  mkpath demo/one
  run env -u CI_PIPELINE_NUMBER bash "$EX" --dry-run
  [ "$status" -eq 0 ]
  [[ "$output" =~ run\ Job\ gp-demo-one-h[0-9]+/ ]] || { echo "$output"; return 1; }
}

@test "a GOLDEN_PATH_RUN_ID that would make an invalid k8s name fails closed with a reason (exit 2)" {
  mkpath demo/one
  GOLDEN_PATH_RUN_ID='Bad_ID!' run bash "$EX" --dry-run
  [ "$status" -eq 2 ]
  [[ "$output" == *"GOLDEN_PATH_RUN_ID"* ]] || { echo "$output"; return 1; }
}

@test "the live run deletes, applies, waits on and tears down ONLY its own run-scoped Job" {
  mkpath demo/one
  setup_stubs
  stub buildctl 0 ''
  stub_dispatch kubectl
  stub_case kubectl 'wait' 0 ''
  CI_PIPELINE_NUMBER=240 run bash "$EX" demo/one
  [ "$status" -eq 0 ] || { echo "$output"; teardown_stubs; return 1; }
  called_with kubectl 'delete job gp-demo-one-p240'
  called_with kubectl 'job/gp-demo-one-p240'
  # never the unscoped name another pipeline is using
  ! calls_to kubectl | grep -qE 'gp-demo-one( |$)' || { calls_to kubectl; teardown_stubs; return 1; }
  teardown_stubs
}
