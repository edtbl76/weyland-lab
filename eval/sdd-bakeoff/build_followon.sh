#!/usr/bin/env bash
# Layer 2 of the outcome evaluation: build one follow-on repo per round-1 trial, trials2/<task>-<arm>/.
# Copy of the round-1 repo as it ended (its round-1 changes committed as one commit, so the follow-on diff stands
# alone), with: TASK.md = the follow-on change request; every authored artifact the framework left kept (specs, plans,
# codekb — the next developer may read them); the framework's skills (.claude/) removed and CLAUDE.md = @AGENTS.md, so
# every follow-on is done by the same plain Claude Code. Refuses to overwrite an existing follow-on repo.
set -euo pipefail
B="${SDD_BAKEOFF_HOME:-/home/edwardmangini/sdd-bakeoff}"   # work dir: trials, results, toolbox (outside the repo)
C="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # harness code: eval/sdd-bakeoff in the repo
mkdir -p "$B/trials2"
for task in ${TASKS:-small brown green}; do
  for arm in ${ARMS:-none aidlc bmad openspec speckit}; do
    src="$B/trials/$task-$arm"; d="$B/trials2/$task-$arm"
    [ -e "$d" ] && { echo "exists, skipping: $d"; continue; }
    cp -a "$src" "$d"
    git -C "$d" add -A
    git -C "$d" commit -q -m "round-1 output ($arm)" || true
    if [ -d "$d/.claude" ]; then mv "$d/.claude" "$B/reference/.removed-followon-claude-$task-$arm"; fi
    printf '@AGENTS.md\n' > "$d/CLAUDE.md"
    cp "$C/reference/task2-$task.md" "$d/TASK.md"
    git -C "$d" add -A
    git -C "$d" commit -q -m "follow-on base: $task ($arm output, plain agent)"
    echo "built follow-on $task-$arm ($(git -C "$d" rev-list --count HEAD) commits)"
  done
done
