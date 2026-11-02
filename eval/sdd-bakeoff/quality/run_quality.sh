#!/usr/bin/env bash
# Layer 1 of the outcome evaluation: static quality + test-strength (mutation) for one trial, in a throwaway
# container on a COPY of the trial (the trial repo itself is mounted read-only and never modified).
#   usage: run_quality.sh <task> <arm>        → results/quality/<task>-<arm>.txt
set -uo pipefail
task="$1"; arm="$2"
B="${SDD_BAKEOFF_HOME:-/home/edwardmangini/sdd-bakeoff}"   # work dir: trials, results, toolbox (outside the repo)
C="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"   # harness code: eval/sdd-bakeoff in the repo
mkdir -p "$B/results/quality"
# /q = this harness's quality code (repo); /t = binaries from the work dir's toolbox (promtool 3.5.3, bats-core 1.14),
# which are too large for the repo
docker run --rm -e TASK="$task" -v "$B/trials/$task-$arm":/src:ro -v "$C/quality":/q:ro \
  -v "$B/toolbox/bin/promtool":/t/promtool:ro -v "$B/toolbox/bats-core":/t/bats-core:ro python:3.12-slim \
  bash -c 'cp -r /src /w && bash /q/in_container.sh' > "$B/results/quality/$task-$arm.txt" 2>&1
grep -E "^(mutation|ruff_findings|ccn_max|radon_mi|error)" "$B/results/quality/$task-$arm.txt" | tr '\n' ' '
echo
