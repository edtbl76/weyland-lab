#!/usr/bin/env bats
# B175 — scripts/check-loop-library.sh, the repo guard for the loop library.
#
# Two failures it exists to catch: a loop without a checkable terminal condition (EMA-233's acceptance rule), and a
# published bundle that has drifted from the Markdown source (the Dagster image publishes the BUNDLE, so a stale one
# silently serves old loops). Exit codes are the contract: 0 valid and in sync · 1 a real defect · 2 could not run.
# Each test asserts the reason in the output, not just the status.

setup() {
  load helper
  GUARD="$REPO_ROOT/scripts/check-loop-library.sh"
  EMBED="$REPO_ROOT/scripts/embed-loops.sh"
  T="$(mktemp -d)"
  mkdir -p "$T/lib"
  cat >"$T/lib/ci-watch.md" <<'EOF'
---
id: ci-watch
title: The CI watch
category: Operations
description: Watch a pipeline to a terminal state.
terminal_condition: The pipeline reaches success, or the same step fails twice after a fix.
---

## Prompt

Trigger it, then check it.
EOF
  export LOOP_LIBRARY_DIR="$T/lib" LOOP_LIBRARY_BUNDLE="$T/loop_library.json"
}

teardown() {
  rm -rf "$T"
}

@test "the real library is valid and its bundle is in sync" {
  unset LOOP_LIBRARY_DIR LOOP_LIBRARY_BUNDLE
  run bash "$GUARD"
  [ "$status" -eq 0 ]
  [[ "$output" == *"terminal condition"*"bundle in sync"* ]]
}

@test "embed writes the bundle and the guard then passes" {
  run bash "$EMBED"
  [ "$status" -eq 0 ]
  [ -s "$LOOP_LIBRARY_BUNDLE" ]
  run bash "$GUARD"
  [ "$status" -eq 0 ]
}

@test "a loop without a terminal condition fails by name" {
  sed -i '/^terminal_condition:/d' "$T/lib/ci-watch.md"
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"ci-watch.md: missing terminal_condition"* ]]
}

@test "a stale bundle fails and says to re-embed" {
  bash "$EMBED"
  sed -i 's/Trigger it, then check it./Trigger it, then check it twice./' "$T/lib/ci-watch.md"
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"bundle is stale"*"embed-loops.sh"* ]]
}

@test "a missing bundle fails, it is not treated as in sync" {
  run bash "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"bundle is stale"* ]]
}

@test "an empty library is exit 2, never valid" {
  rm "$T/lib/ci-watch.md"
  run bash "$GUARD"
  [ "$status" -eq 2 ]
  [[ "$output" == *"no loops"* ]]
}

@test "embed refuses to write a bundle from an invalid library" {
  sed -i 's/^category: Operations/category: Misc/' "$T/lib/ci-watch.md"
  run bash "$EMBED"
  [ "$status" -eq 1 ]
  [ ! -e "$LOOP_LIBRARY_BUNDLE" ]
}
