#!/usr/bin/env bash
# realm-eval.sh — run the B253 Realm of Agents evaluation (2026-11-20) in batches, resumably.
#   run     plan locally, run each batch in-cluster (kubectl exec into dagster-user-code: the Realm's NetworkPolicy
#           admits it), append one line per run to results.jsonl. Free-only: the Realm's /eval/run spends nothing.
#   judge   blind-score every successful run with wl-judge-oss (in the same pod, which holds LITELLM_*), append to
#           scores.jsonl. Only valid scores count as progress; a judge error is rerun on the next pass.
#   report  write report.md from the tasks, results and scores (refuses while a successful run is unjudged).
# Stops cleanly when nothing is left; stops with exit 1 after two batches in a row make no progress (never spins
# all night); a dropped exec keeps every line that finished. Logic and modes: realm_eval.py.
# Runbook: docs/runbooks/realm-of-agents.md § Evaluation (B253).
#
# Exit: 0 done · 1 no progress (named) or report refused · 2 usage
set -euo pipefail
S="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PY="$S/realm_eval.py"
TASKS="${REALM_EVAL_TASKS:-$S/../services/weyland-dagster/weyland_pipeline/eval_sets/realm.json}"
OUT="${REALM_EVAL_DIR:-$HOME/IdeaProjects/weyland/eval/realm-b253}"
REPS="${REALM_EVAL_REPS:-3}"
BATCH="${REALM_EVAL_BATCH:-6}"
POD="${REALM_EVAL_POD:-deploy/dagster-user-code}"

mode="${1:-}"
case "$mode" in run|judge|report) ;; *) echo "usage: realm-eval.sh {run|judge|report}" >&2; exit 2 ;; esac

mkdir -p "$OUT"
R="$OUT/results.jsonl"; SC="$OUT/scores.jsonl"
touch "$R" "$SC"

in_cluster() {   # $1 = run | judge; the batch on stdin
  kubectl -n weyland exec -i "$POD" -c dagster-user-code -- python -c "$(cat "$PY")" "$1"
}

progress() {     # what counts as done: every result line (a failed run is done); only valid scores
  if [ "$1" = run ]; then grep -c . "$R" || true; else grep -c '"ok": true' "$SC" || true; fi
}

loop() {         # $1 = run | judge
  local planner out stalls=0 batch before after
  if [ "$1" = run ]; then planner=plan; out="$R"; else planner=judge-plan; out="$SC"; fi
  while :; do
    batch="$(python3 "$PY" "$planner" --tasks "$TASKS" --results "$R" --scores "$SC" --reps "$REPS" --limit "$BATCH")"
    if [ -z "$batch" ]; then
      echo "$1: nothing left to do ($(progress "$1") done)" >&2
      return 0
    fi
    before="$(progress "$1")"
    printf '%s\n' "$batch" | in_cluster "$1" >> "$out" || echo "$1: the exec ended early (kept what finished)" >&2
    after="$(progress "$1")"
    if [ "$after" -le "$before" ]; then
      stalls=$((stalls + 1))
      if [ "$stalls" -ge 2 ]; then
        echo "$1: no progress in two batches in a row; stopping (see the lines above)" >&2
        return 1
      fi
    else
      stalls=0
    fi
  done
}

if [ "$mode" = report ]; then
  python3 "$PY" report --tasks "$TASKS" --results "$R" --scores "$SC" > "$OUT/report.md.tmp"
  mv "$OUT/report.md.tmp" "$OUT/report.md"
  echo "wrote $OUT/report.md" >&2
  exit 0
fi
loop "$mode"
