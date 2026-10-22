#!/usr/bin/env bash
# emdash-worktree-sweep.sh (B179, 2026-10-22) — remove the Emdash run worktrees that hold nothing. Run daily at 06:30 NY
# by the user timer nodes/rogueone/systemd/emdash-worktree-sweep.{service,timer}.
#
# WHY: every `agent-ready-nightly` run opens a worktree under ~/emdash/worktrees/<project>/emdash-<id> on a branch of the
# same name, even on a night with no `agent-ready` issue, and nothing removed them: 10 had piled up by 2026-10-22, all
# empty. A worktree is removed (`git worktree remove` + `git branch -D`) only when ALL hold:
#   - no uncommitted or untracked change (`git status --porcelain` is empty),
#   - no commit that is not on origin/main (as this repo last fetched it; a stale origin/main can only KEEP more),
#   - older than EMDASH_SWEEP_MIN_AGE_H (default 24 h, by the worktree's .git file), so a run in progress is never touched.
# Anything else is kept and named for the owner. Only worktrees under EMDASH_WORKTREES on an `emdash-` branch are
# considered; every other worktree is ignored.
#
#   usage: scripts/emdash-worktree-sweep.sh [--apply]      (without --apply: list what it would remove, remove nothing)
# EXIT: 0 done (removed, kept or nothing to do) · 2 could not check (no repository, no origin/main, a git failure).
# Tests: scripts/tests/emdash-worktree-sweep.bats. Runbook: docs/runbooks/software-factory.md § Worktree sweep.
set -uo pipefail
REPO="${EMDASH_SWEEP_REPO:-$HOME/IdeaProjects/weyland}"
ROOT="${EMDASH_WORKTREES:-$HOME/emdash/worktrees}"
MIN_AGE_H="${EMDASH_SWEEP_MIN_AGE_H:-24}"
APPLY=0
case "${1:-}" in
  --apply) APPLY=1 ;;
  "") ;;
  *) echo "usage: $0 [--apply]" >&2; exit 2 ;;
esac

cannot() { echo "CANNOT CHECK: $*"; exit 2; }
git -C "$REPO" rev-parse --git-dir >/dev/null 2>&1 || cannot "$REPO is not a git repository"
git -C "$REPO" rev-parse --verify -q refs/remotes/origin/main >/dev/null \
  || cannot "$REPO has no origin/main, so unpushed work cannot be told apart"
list="$(git -C "$REPO" worktree list --porcelain)" || cannot "git worktree list failed in $REPO"
ROOT="$(cd "$ROOT" 2>/dev/null && pwd -P || echo "$ROOT")"

now="$(date +%s)"
removed=0 kept=0 path="" branch=""
consider() {
  [ -n "$path" ] && [ -n "$branch" ] || return 0
  case "$path" in "$ROOT"/*) ;; *) return 0 ;; esac
  case "$branch" in emdash-*) ;; *) return 0 ;; esac
  local name age_h dirty ahead
  name="$(basename "$path")"
  age_h=$(( (now - $(stat -c %Y "$path/.git")) / 3600 ))
  dirty="$(git -C "$path" status --porcelain 2>/dev/null)" || { echo "kept $name: git status failed"; kept=$((kept+1)); return 0; }
  ahead="$(git -C "$path" rev-list --count refs/remotes/origin/main..HEAD 2>/dev/null)" \
    || { echo "kept $name: could not compare with origin/main"; kept=$((kept+1)); return 0; }
  if [ -n "$dirty" ]; then
    echo "kept $name: uncommitted or untracked changes ($path)"; kept=$((kept+1))
  elif [ "$ahead" -gt 0 ]; then
    echo "kept $name: $ahead commit(s) not on origin/main ($path)"; kept=$((kept+1))
  elif [ "$age_h" -lt "$MIN_AGE_H" ]; then
    echo "kept $name: younger than $MIN_AGE_H h (${age_h} h; may still be running)"; kept=$((kept+1))
  elif [ "$APPLY" = 0 ]; then
    echo "would remove $name (empty, ${age_h} h old)"
  elif git -C "$REPO" worktree remove "$path" && git -C "$REPO" branch -D -q "$branch"; then
    echo "removed $name (empty, ${age_h} h old)"; removed=$((removed+1))
  else
    echo "kept $name: git worktree remove / branch -D failed"; kept=$((kept+1))
  fi
}
while IFS= read -r line; do
  case "$line" in
    "worktree "*) consider; path="${line#worktree }"; branch="" ;;
    "branch refs/heads/"*) branch="${line#branch refs/heads/}" ;;
  esac
done <<<"$list"
consider
echo "OK — $removed removed, $kept kept$([ "$APPLY" = 0 ] && echo ' (dry run: pass --apply to remove)')."
