#!/usr/bin/env bash
# Grader for py-median-bug. Runs the task's own test suite inside the run
# workdir (the runner cd's here first). Emits a single authoritative verdict
# line — `GRADE: PASS` or `GRADE: FAIL` — as its LAST line, and exits 0/1 to
# match. Fail-closed: any path that does not run the tests emits GRADE: FAIL.
set -uo pipefail

command -v python3 >/dev/null 2>&1 || { echo "grader: python3 not found" >&2; echo "GRADE: FAIL"; exit 1; }
[ -f test_stats.py ] || { echo "grader: test_stats.py missing" >&2; echo "GRADE: FAIL"; exit 1; }

# Run the suite. -v so the runner log shows which cases ran; the sentinel below
# is what the runner keys on, never this command's bare exit code alone.
if python3 -m unittest -v test_stats >grade.out 2>&1; then
  # unittest prints "OK" only when it actually executed and all passed. Require
  # that token so a zero exit from an empty/erroring run cannot pass.
  if grep -qE '^OK' grade.out; then
    cat grade.out
    echo "GRADE: PASS"; exit 0
  fi
fi
cat grade.out 2>/dev/null
echo "GRADE: FAIL"; exit 1
