#!/usr/bin/env bash
# Re-run every OpenSpec trial that started on Node 18, 2 at a time (as the replicate batches run), then rebuild what
# round 1 feeds: the follow-on repos + their follow-on runs, the docs-ablation repos, the planted defects and the
# oracle review repos. Run AFTER redo_openspec_node18.sh, and only when no other batch is running.
set -uo pipefail
B="${SDD_BAKEOFF_HOME:-/home/edwardmangini/sdd-bakeoff}"   # work dir: trials, results, toolbox (outside the repo)
C="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # harness code: eval/sdd-bakeoff in the repo
S="$B/results/summary.tsv"
[ -e "$S.pre-node18" ] || cp "$S" "$S.pre-node18"
grep -v -P '^\S+\topenspec\t' "$S.pre-node18" > "$S"
printf '%s\n' "small" "brown" "green" "vague" "brown -r3" "small -r3" "vague -r3" | xargs -P 2 -L 1 bash "$C/redo_job.sh"
echo "=== $(date -u +%T) round 1 + replicates done; follow-ons"
TASKS="small brown green vague" bash "$C/build_followon.sh" | grep openspec
for task in small brown green vague; do
  [ -e "$B/results2/$task-openspec.jsonl" ] && continue
  bash "$C/run_followon.sh" "$task" openspec
done
python3 "$C/build_nodocs.py" | grep openspec
python3 "$C/select_defects.py" small-openspec brown-openspec green-openspec vague-openspec | grep '^=='
python3 "$C/build_review.py" | grep openspec
echo "=== openspec redo done $(date -u +%T)"
