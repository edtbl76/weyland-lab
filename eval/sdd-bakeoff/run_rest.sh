#!/usr/bin/env bash
# The rest of the scaled plan, in order, 2 runs at a time throughout:
#   1. replicate batch 2 (the last 20 of the 40 replicates)
#   2. docs ablation: the 16 framework follow-ons on trials3 (framework documents removed) → results3/
#   3. spec-as-oracle: the 36 read-only reviews in results/oracle/cases.tsv, then score them
# Every step is resumable (each runner refuses a run that already has a result).
set -uo pipefail
B="${SDD_BAKEOFF_HOME:-/home/edwardmangini/sdd-bakeoff}"   # work dir: trials, results, toolbox (outside the repo)
C="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # harness code: eval/sdd-bakeoff in the repo
echo "=== $(date -u +%T) replicate batch 2"
bash "$C/run_reps.sh" 2
echo "=== $(date -u +%T) docs ablation"
for t in small brown green vague; do for a in aidlc bmad openspec speckit; do echo "$t $a"; done; done \
  | TRIALS_DIR=trials3 RESULTS_DIR=results3 xargs -P 2 -L 1 bash "$C/run_followon.sh"
echo "=== $(date -u +%T) oracle reviews"
tail -n +2 "$B/results/oracle/cases.tsv" | cut -f1-4 | tr '\t' ' ' | xargs -P 2 -L 1 bash "$C/run_review.sh"
python3 "$C/score_reviews.py"
echo "=== rest done $(date -u +%T)"
