#!/usr/bin/env bats
# Run ONLY by `run-lang-tests.sh shell --self-check`. MUST fail — that is the point.
# Normal runs use `bats .`, which does not descend into this directory.

@test "deliberate failure (proves the shell lane can fail)" {
  run false
  [ "$status" -eq 0 ]
}
