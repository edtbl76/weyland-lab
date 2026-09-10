#!/usr/bin/env bash
# Grader for js-parse-range-bug. Runs the task's node:test suite in the run
# workdir (the runner cd's here first). Emits `GRADE: PASS`/`GRADE: FAIL` as its
# LAST line and exits 0/1 to match. Fail-closed: any path that does not run the
# tests emits GRADE: FAIL.
set -uo pipefail

command -v node >/dev/null 2>&1 || { echo "grader: node not found" >&2; echo "GRADE: FAIL"; exit 1; }
[ -f test.js ] || { echo "grader: test.js missing" >&2; echo "GRADE: FAIL"; exit 1; }

if node --test --test-reporter=tap >grade.out 2>&1; then
  # The TAP reporter prints a stable machine-readable summary (`# pass N` /
  # `# fail 0`). Require a real pass count AND zero fails so an empty or errored
  # run cannot be mistaken for success. (The default spec reporter prints
  # `ℹ pass N` with ANSI/glyph prefixes — do not key on that.)
  if grep -qE '^# pass [1-9]' grade.out && grep -qE '^# fail 0$' grade.out; then
    cat grade.out
    echo "GRADE: PASS"; exit 0
  fi
fi
cat grade.out 2>/dev/null
echo "GRADE: FAIL"; exit 1
