#!/usr/bin/env bash
# One OpenSpec re-run on Node 24 (see redo_openspec_node18.sh). usage: redo_job.sh <task> [suffix]
# Round 1 (no suffix): run, judge, layer-1 quality, one line to results/summary.tsv (small/brown/green; vague has none).
# A replicate (-r2/-r3): rep_job.sh, which runs, judges and appends to results/replicates.tsv.
# Either way it records how often the Node 18 crash appeared, which must be 0 now.
set -uo pipefail
task="$1"; suf="${2:-}"
B="${SDD_BAKEOFF_HOME:-/home/edwardmangini/sdd-bakeoff}"   # work dir: trials, results, toolbox (outside the repo)
C="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # harness code: eval/sdd-bakeoff in the repo
id="$task-openspec$suf"
if [ -n "$suf" ]; then
  bash "$C/rep_job.sh" "$task" openspec "$suf" > /dev/null
  judge=$(tail -1 "$B/results/$id.judge" 2>/dev/null)
else
  [ -e "$B/results/$id.jsonl" ] && { echo "skip $id"; exit 0; }
  bash "$C/run_trial.sh" "$task" openspec > /dev/null
  judge=$(bash "$C/judge_trial.sh" "$task" openspec | tail -1)
  if [ "$task" != vague ]; then
    stats=$(python3 "$C/run_stats.py" "$B/results/$id.jsonl")
    rc=$(sed -n 's/.*exit=\([0-9]*\).*/\1/p' "$B/results/$id.meta" | head -1)
    fc=$(sed -n 's/^files_changed=//p' "$B/results/$id.meta")
    missing=$(grep -oE '[A-Za-z0-9_.-]+: command not found' "$B/results/$id.jsonl" | sort | uniq -c | awk '{printf "%s:%s ", $2, $1}')
    line=$(printf '%s\t%s\t%s\t%s\t%s\t%s\t%s' "$task" openspec "$rc" "$judge" "$stats" "$fc" "${missing:-none}")
    flock "$B/results/replicates.lock" -c "printf '%s\n' \"$line\" >> '$B/results/summary.tsv'"
  fi
  bash "$C/quality/run_quality.sh" "$task" openspec > /dev/null
fi
crash=$(grep -c "Unexpected token 'with'" "$B/results/$id.jsonl")
calls=$(grep -oE '"command":"[^"]{0,60}openspec (new|status|instructions|validate|archive|list)' "$B/results/$id.jsonl" | wc -l)
echo "$(date -u +%T) $id | $judge | openspec CLI calls=$calls node18-crash=$crash"
