#!/usr/bin/env bash
# The vague task end to end, one trial at a time: round 1 for all five arms (judged), then a follow-on repo per arm
# and its plain-agent follow-on change (judged). Resumable (each step refuses to redo a finished trial).
set -uo pipefail
B="${SDD_BAKEOFF_HOME:-/home/edwardmangini/sdd-bakeoff}"   # work dir: trials, results, toolbox (outside the repo)
C="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # harness code: eval/sdd-bakeoff in the repo
for arm in speckit none bmad aidlc openspec; do
  if [ ! -e "$B/results/vague-$arm.jsonl" ]; then
    echo "=== $(date -u +%T) round-1 vague-$arm"
    bash "$C/run_trial.sh" vague "$arm"
    echo "    $(bash "$C/judge_trial.sh" vague "$arm" | tail -1) | missing: $(grep -oE '[A-Za-z0-9_.-]+: command not found' "$B/results/vague-$arm.jsonl" | sort | uniq -c | awk '{printf "%s:%s ", $2, $1}')"
  fi
done
TASKS=vague bash "$C/build_followon.sh" | grep -v "exists, skipping"
for arm in openspec aidlc speckit bmad none; do
  [ -e "$B/results2/vague-$arm.jsonl" ] && continue
  echo "=== $(date -u +%T) follow-on vague-$arm"
  bash "$C/run_followon.sh" vague "$arm"
done
echo "=== vague done $(date -u +%T)"
