#!/usr/bin/env bash
# OpenSpec 1.16.0 needs Node >= 22.12; the trials' PATH had only /usr/bin/node (v18), so `openspec new change` crashed
# (SyntaxError: Unexpected token 'with') in every OpenSpec run up to 2026-11-01. Node 24.1.0 is now toolbox/bin/node.
# This script archives every OpenSpec run that STARTED on Node 18, and everything derived from it, to
# invalid/<id>-node18/, then rebuilds those trial repos exactly as before (base snapshot + `openspec init`).
#   usage: redo_openspec_node18.sh   (idempotent: skips an id already archived)
set -uo pipefail
B="${SDD_BAKEOFF_HOME:-/home/edwardmangini/sdd-bakeoff}"   # work dir: trials, results, toolbox (outside the repo)
C="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # harness code: eval/sdd-bakeoff in the repo
REASON="node18: OpenSpec 1.16.0 needs Node >= 22.12; openspec new change crashed (Unexpected token 'with')"
ROUND1="small-openspec brown-openspec green-openspec vague-openspec"
REPS="brown-openspec-r3 small-openspec-r3 vague-openspec-r3"

for id in $ROUND1 $REPS; do
  A="$B/invalid/$id-node18"
  [ -e "$A" ] && { echo "already archived $id"; continue; }
  mkdir -p "$A/results" "$A/derived"
  for f in "$B/results/$id".{err,jsonl,judge,meta} "$B/results/$id-mut.judge" "$B/results/quality/$id.txt"; do
    [ -e "$f" ] && mv "$f" "$A/results/"
  done
  [ -d "$B/trials/$id" ] && mv "$B/trials/$id" "$A/trial"
  [ -d "$B/tmp/$id" ] && mv "$B/tmp/$id" "$A/tmp"
  case " $ROUND1 " in *" $id "*)
    # round 1 feeds the follow-on (trials2/results2), the docs ablation (trials3) and the oracle (trials4)
    for f in "$B/results2/$id".{err,jsonl,judge,meta}; do [ -e "$f" ] && mv "$f" "$A/derived/"; done
    [ -d "$B/trials2/$id" ] && mv "$B/trials2/$id" "$A/derived/trials2"
    [ -d "$B/tmp2/$id" ] && mv "$B/tmp2/$id" "$A/derived/tmp2"
    [ -d "$B/trials3/$id" ] && mv "$B/trials3/$id" "$A/derived/trials3"
    for v in docs nodocs; do [ -d "$B/trials4/$id-$v" ] && mv "$B/trials4/$id-$v" "$A/derived/trials4-$v"; done
    task=${id%%-*}
    printf '%s\topenspec\tINVALID\t%s; archived to invalid/%s-node18\n' "$task" "$REASON" "$id" >> "$B/results/invalid.tsv"
    ;;
  esac
  echo "$REASON" > "$A/REASON"
  echo "archived $id"
done

# drop the archived rows from the shared ledgers (originals kept beside them)
for f in replicates.tsv oracle/defects.tsv oracle/cases.tsv; do
  p="$B/results/$f"
  [ -e "$p.pre-node18" ] || cp "$p" "$p.pre-node18"
done
grep -v -P '^\S+\topenspec\t-r3\t' "$B/results/replicates.tsv.pre-node18" > "$B/results/replicates.tsv"
grep -v -P '^\S+\topenspec\t' "$B/results/oracle/defects.tsv.pre-node18" > "$B/results/oracle/defects.tsv"
grep -v -P '^\S+\topenspec\t' "$B/results/oracle/cases.tsv.pre-node18" > "$B/results/oracle/cases.tsv"

# rebuild the trial repos: same base snapshot, same OpenSpec install, same two commits
for id in $ROUND1 $REPS; do
  task=${id%%-*}; suf=${id#*-openspec}
  d="$B/trials/$id"
  [ -e "$d" ] && { echo "trial exists, not rebuilt: $id"; continue; }
  # build_trials.sh parks the removed dirs under reference/.removed-*; move the old ones aside so mv cannot nest
  for r in "$B/reference/.removed-store-scaler-openspec$suf" "$B/reference/.removed-claude-$task-openspec$suf" \
           "$B/reference/.removed-aidlc-$task-openspec$suf"; do
    [ -e "$r" ] && mv "$r" "$B/invalid/$id-node18/derived/$(basename "$r")"
  done
  TASKS="$task" SUFFIX="$suf" bash "$C/build_trials.sh" | grep -F "$id" || true
  # build_trials.sh builds every arm; only the openspec one is wanted, the others already exist and are skipped
  npx --yes @fission-ai/openspec@1.16.0 init --tools claude --no-animation "$d" > /dev/null 2>&1 \
    || { echo "openspec init FAILED for $id"; exit 1; }
  git -C "$d" add -A
  git -C "$d" commit -q -m "framework installed"
  echo "rebuilt $id ($(git -C "$d" rev-list --count HEAD) commits)"
done
