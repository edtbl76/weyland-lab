#!/usr/bin/env bash
# The AI-DLC 2.11.2 arm end to end: 12 runs (4 tasks x r1-r3) with the click-through driver, 2 at a time in a seeded
# shuffled order, each judged and appended to results/replicates.tsv; then layer-1 quality for each, and the follow-on
# (plain Claude Code) for the 4 round-1 outputs. Resumable: every step refuses a run that already has a result.
set -uo pipefail
B="${SDD_BAKEOFF_HOME:-/home/edwardmangini/sdd-bakeoff}"   # work dir: trials, results, toolbox (outside the repo)
C="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # harness code: eval/sdd-bakeoff in the repo
job() {   # job <task> <r1|r2|r3>
  local task="$1" rep="$2" suf="-$2" id
  [ "$rep" = r1 ] && suf=""
  id="$task-aidlc211$suf"
  [ -e "$B/results/$id.jsonl" ] && { echo "skip $id"; return; }
  bash "$C/run_trial.sh" "$task" aidlc211 "$suf" > /dev/null
  local judge replies missing
  judge=$(bash "$C/judge_trial.sh" "$task" aidlc211 "$suf" | tail -1)
  replies=$(sed -n 's/^human_replies=//p' "$B/results/$id.meta")
  missing=$(grep -oE '[A-Za-z0-9_.-]+: command not found' "$B/results/$id.jsonl" | sort | uniq -c | awk '{printf "%s:%s ", $2, $1}')
  flock "$B/results/replicates.lock" -c "printf '%s\t%s\t%s\t%s\t%s\n' '$task' aidlc211 '${suf:--r1}' '$judge' '${missing:-none}' >> '$B/results/replicates.tsv'"
  bash "$C/quality/run_quality.sh" "$task" "aidlc211$suf" > /dev/null
  echo "$(date -u +%T) $id | $judge | human replies=$replies | missing: ${missing:-none}"
}
export -f job
export B
for t in small brown green vague; do for r in r1 r2 r3; do echo "$t $r"; done; done \
  | python3 -c 'import random, sys; l = sys.stdin.read().split("\n")[:-1]; random.Random(211).shuffle(l); print("\n".join(l))' \
  | xargs -P 2 -L 1 bash -c 'job "$0" "$1"'
echo "=== $(date -u +%T) runs done; follow-ons"
TASKS="small brown green vague" ARMS=aidlc211 bash "$C/build_followon.sh" | grep aidlc211
for t in small brown green vague; do
  [ -e "$B/results2/$t-aidlc211.jsonl" ] && continue
  bash "$C/run_followon.sh" "$t" aidlc211
done
echo "=== aidlc211 done $(date -u +%T)"
