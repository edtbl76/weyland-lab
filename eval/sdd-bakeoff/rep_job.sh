#!/usr/bin/env bash
# One replicate job: run, judge, flag missing runtimes, append one locked line to results/replicates.tsv.
#   usage: rep_job.sh <task> <arm> <suffix>
set -uo pipefail
task="$1"; arm="$2"; suf="$3"
B="${SDD_BAKEOFF_HOME:-/home/edwardmangini/sdd-bakeoff}"   # work dir: trials, results, toolbox (outside the repo)
C="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # harness code: eval/sdd-bakeoff in the repo
[ -e "$B/results/$task-$arm$suf.jsonl" ] && { echo "skip $task-$arm$suf"; exit 0; }
bash "$C/run_trial.sh" "$task" "$arm" "$suf" > /dev/null
judge=$(bash "$C/judge_trial.sh" "$task" "$arm" "$suf" | tail -1)
missing=$(grep -oE '[A-Za-z0-9_.-]+: command not found' "$B/results/$task-$arm$suf.jsonl" | sort | uniq -c | awk '{printf "%s:%s ", $2, $1}')
line=$(printf '%s\t%s\t%s\t%s\t%s' "$task" "$arm" "$suf" "$judge" "${missing:-none}")
flock "$B/results/replicates.lock" -c "printf '%s\n' \"$line\" >> '$B/results/replicates.tsv'"
echo "$(date -u +%T) $task-$arm$suf | $judge | missing: ${missing:-none}"
