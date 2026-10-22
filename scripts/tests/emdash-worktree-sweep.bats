#!/usr/bin/env bats
# emdash-worktree-sweep.sh (B179, 2026-10-22) — removes the Emdash run worktrees that hold nothing. Every nightly
# `agent-ready-nightly` run opens a worktree + branch `emdash-<id>`, even on a night with no `agent-ready` issue, and
# nothing removed them (10 by 2026-10-22, all empty). A worktree is removed only when it has no uncommitted or untracked
# change, no commit that is not on origin/main, and is older than the age floor; anything else is kept and named.
# These run REAL git (a bare origin, a clone, real worktrees), not stubs: the contract under test is git's.
# EXIT: 0 done (removed, kept or nothing) · 2 could not check (no repo, no origin/main, a git failure).

setup() {
  S="$BATS_TEST_DIRNAME/../emdash-worktree-sweep.sh"
  T="$BATS_TEST_TMPDIR"
  export GIT_AUTHOR_NAME=t GIT_AUTHOR_EMAIL=t@t GIT_COMMITTER_NAME=t GIT_COMMITTER_EMAIL=t@t
  git init -q --bare -b main "$T/origin.git"
  git clone -q "$T/origin.git" "$T/repo" 2>/dev/null
  git -C "$T/repo" commit -q --allow-empty -m init
  git -C "$T/repo" push -q origin main
  export EMDASH_SWEEP_REPO="$T/repo" EMDASH_WORKTREES="$T/worktrees"
  mkdir -p "$EMDASH_WORKTREES/weyland-x"
}

# age <path> <seconds ago> — set mtime portably (CI's bats image is BusyBox: `touch -d "3 days ago"` is invalid there)
age() { python3 -c 'import os,sys,time; t=time.time()-int(sys.argv[2]); os.utime(sys.argv[1],(t,t))' "$1" "$2"; }

# wt <name> <seconds ago> — an Emdash-style worktree on branch <name> from origin/main
wt() {
  git -C "$T/repo" worktree add -q -b "$1" "$EMDASH_WORKTREES/weyland-x/$1" origin/main
  age "$EMDASH_WORKTREES/weyland-x/$1/.git" "$2"
}

@test "an empty run worktree older than a day is removed with its branch" {
  wt emdash-aaa 259200
  run bash "$S" --apply
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"removed emdash-aaa"* ]] || { echo "$output"; return 1; }
  [ ! -d "$EMDASH_WORKTREES/weyland-x/emdash-aaa" ]
  if git -C "$T/repo" show-ref --verify -q refs/heads/emdash-aaa; then return 1; fi
}

@test "uncommitted work keeps the worktree" {
  wt emdash-bbb 259200
  echo change > "$EMDASH_WORKTREES/weyland-x/emdash-bbb/new.txt"
  run bash "$S" --apply
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"kept emdash-bbb: uncommitted or untracked changes"* ]] || { echo "$output"; return 1; }
  [ -f "$EMDASH_WORKTREES/weyland-x/emdash-bbb/new.txt" ]
}

@test "a commit not on origin/main keeps the worktree" {
  wt emdash-ccc 259200
  git -C "$EMDASH_WORKTREES/weyland-x/emdash-ccc" commit -q --allow-empty -m work
  age "$EMDASH_WORKTREES/weyland-x/emdash-ccc/.git" 259200
  run bash "$S" --apply
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"kept emdash-ccc: 1 commit(s) not on origin/main"* ]] || { echo "$output"; return 1; }
  git -C "$T/repo" show-ref --verify -q refs/heads/emdash-ccc
}

@test "a run younger than the age floor is kept (it may still be running)" {
  wt emdash-ddd 3600
  run bash "$S" --apply
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"kept emdash-ddd: younger than 24 h"* ]] || { echo "$output"; return 1; }
  [ -d "$EMDASH_WORKTREES/weyland-x/emdash-ddd" ]
}

@test "without --apply nothing is removed, only listed" {
  wt emdash-eee 259200
  run bash "$S"
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [[ "$output" == *"would remove emdash-eee"* ]] || { echo "$output"; return 1; }
  [ -d "$EMDASH_WORKTREES/weyland-x/emdash-eee" ]
}

@test "a worktree outside the Emdash directory, or not on an emdash- branch, is never touched" {
  git -C "$T/repo" worktree add -q -b feature "$T/elsewhere" origin/main
  age "$T/elsewhere/.git" 259200
  git -C "$T/repo" worktree add -q -b other "$EMDASH_WORKTREES/weyland-x/other" origin/main
  age "$EMDASH_WORKTREES/weyland-x/other/.git" 259200
  run bash "$S" --apply
  [ "$status" -eq 0 ] || { echo "$output"; return 1; }
  [ -d "$T/elsewhere" ] && [ -d "$EMDASH_WORKTREES/weyland-x/other" ]
  [[ "$output" == *"OK — 0 removed, 0 kept"* ]] || { echo "$output"; return 1; }
}

@test "no origin/main is exit 2, never a guess about what is unpushed" {
  wt emdash-fff 259200
  git -C "$T/repo" update-ref -d refs/remotes/origin/main
  run bash "$S" --apply
  [ "$status" -eq 2 ] || { echo "$output"; return 1; }
  [[ "$output" == *"CANNOT CHECK"*"origin/main"* ]] || { echo "$output"; return 1; }
  [ -d "$EMDASH_WORKTREES/weyland-x/emdash-fff" ]
}

@test "a missing repository is exit 2" {
  export EMDASH_SWEEP_REPO="$T/nope"
  run bash "$S" --apply
  [ "$status" -eq 2 ] || { echo "$output"; return 1; }
  [[ "$output" == *"CANNOT CHECK"* ]] || { echo "$output"; return 1; }
}
