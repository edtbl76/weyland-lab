#!/usr/bin/env bash
# Run every B86 bake-off trial one at a time, judge each as it finishes, and append one line per trial to
# results/summary.tsv. Skips trials that already have a result (resumable). Arm order rotates per task so no framework
# always runs first or last (rate limits or quota late in the day cannot land on one arm).
set -uo pipefail
B="${SDD_BAKEOFF_HOME:-/home/edwardmangini/sdd-bakeoff}"   # work dir: trials, results, toolbox (outside the repo)
C="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # harness code: eval/sdd-bakeoff in the repo
S="$B/results/summary.tsv"
[ -f "$S" ] || printf 'task\tarm\texit\tjudge\tturns\tduration_s\tcost_usd_equiv\tout_tokens\tfiles_changed\n' > "$S"
declare -A ORDER=(
  [small]="none aidlc bmad openspec speckit"
  [brown]="openspec speckit none aidlc bmad"
  [green]="bmad openspec speckit none aidlc"
)
for task in small brown green; do
  for arm in ${ORDER[$task]}; do
    [ -e "$B/results/$task-$arm.jsonl" ] && { echo "skip $task-$arm (has result)"; continue; }
    echo "=== $(date -u +%T) run $task-$arm"
    bash "$C/run_trial.sh" "$task" "$arm"
    judge=$(bash "$C/judge_trial.sh" "$task" "$arm" | tail -1)
    stats=$(python3 "$C/run_stats.py" "$B/results/$task-$arm.jsonl")
    rc=$(sed -n 's/.*exit=\([0-9]*\).*/\1/p' "$B/results/$task-$arm.meta" | head -1)
    fc=$(sed -n 's/^files_changed=//p' "$B/results/$task-$arm.meta")
    # A framework whose runtime is missing still "passes" by working around it (found 2026-10-31: AI-DLC without bun,
    # OpenSpec without its CLI). Flag every command-not-found so such a run is never read as a valid result.
    missing=$(grep -oE '[A-Za-z0-9_.-]+: command not found' "$B/results/$task-$arm.jsonl" | sort | uniq -c | awk '{printf "%s:%s ", $2, $1}')
    printf '%s\t%s\t%s\t%s\t%s\t%s\t%s\n' "$task" "$arm" "$rc" "$judge" "$stats" "$fc" "${missing:-none}" >> "$S"
    echo "    $judge | missing commands: ${missing:-none}"
  done
done
echo "=== all done $(date -u +%T)"
