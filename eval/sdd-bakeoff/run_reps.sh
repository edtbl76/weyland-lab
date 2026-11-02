#!/usr/bin/env bash
# Run a batch of the 40 replicate jobs, 2 at a time, in a shuffled order fixed by a seed (reproducible; no arm always
# early or late). usage: run_reps.sh <batch 1|2>   (batch 1 = first 20 of the shuffled list, batch 2 = the rest)
set -uo pipefail
C="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # harness code: eval/sdd-bakeoff in the repo
batch="$1"
jobs=$(for t in small brown green vague; do for a in none aidlc bmad openspec speckit; do for s in -r2 -r3; do echo "$t $a $s"; done; done; done \
       | python3 -c 'import random, sys; l = sys.stdin.read().split("\n")[:-1]; random.Random(86).shuffle(l); print("\n".join(l))')
if [ "$batch" = 1 ]; then sel=$(echo "$jobs" | head -20); else sel=$(echo "$jobs" | tail -20); fi
echo "$sel" | xargs -P 2 -L 1 bash "$C/rep_job.sh"
echo "=== batch $batch done $(date -u +%T)"
