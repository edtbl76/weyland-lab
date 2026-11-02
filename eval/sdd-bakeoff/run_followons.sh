#!/usr/bin/env bash
# Run all 15 follow-on changes one at a time (resumable: run_followon.sh refuses one that already has a result), arm
# order rotated per task, one summary line each → results2/summary.txt
set -uo pipefail
B="${SDD_BAKEOFF_HOME:-/home/edwardmangini/sdd-bakeoff}"   # work dir: trials, results, toolbox (outside the repo)
C="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # harness code: eval/sdd-bakeoff in the repo
declare -A ORDER=(
  [small]="speckit openspec bmad aidlc none"
  [brown]="aidlc none speckit bmad openspec"
  [green]="none speckit aidlc openspec bmad"
)
mkdir -p "$B/results2"
for task in small brown green; do
  for arm in ${ORDER[$task]}; do
    [ -e "$B/results2/$task-$arm.jsonl" ] && { echo "skip $task-$arm"; continue; }
    echo "=== $(date -u +%T) follow-on $task-$arm"
    bash "$C/run_followon.sh" "$task" "$arm" | tee -a "$B/results2/summary.txt"
  done
done
echo "=== all follow-ons done $(date -u +%T)"
