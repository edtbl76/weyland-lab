#!/usr/bin/env bash
# Build the B86 bake-off trial repos: trials/<task>-<arm>/ for task in small/brown/green and arm in
# none/aidlc/bmad/openspec/speckit. Each is a fresh git repo from the task's base snapshot (git archive of the right
# commit, so no later commit — including the real solution — is visible), with TASK.md holding the task text.
# Frameworks are installed afterwards by install_frameworks.sh. Refuses to overwrite an existing trial dir.
set -euo pipefail
B="${SDD_BAKEOFF_HOME:-/home/edwardmangini/sdd-bakeoff}"   # work dir: trials, results, toolbox (outside the repo)
C="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # harness code: eval/sdd-bakeoff in the repo
for task in ${TASKS:-small brown green}; do
  for arm in none aidlc bmad openspec speckit; do
    d="$B/trials/$task-$arm${SUFFIX:-}"
    [ -e "$d" ] && { echo "exists, skipping: $d"; continue; }
    mkdir -p "$d"
    tar -xf "$B/reference/base-$task.tar" -C "$d"
    if [ "$task" = green ]; then
      mv "$d/nodes/mother/lab/weyland-platform/services/store-scaler" "$B/reference/.removed-store-scaler-$arm${SUFFIX:-}"
    fi
    if [ "$arm" != aidlc ]; then
      mv "$d/.claude" "$B/reference/.removed-claude-$task-$arm${SUFFIX:-}"
      mv "$d/aidlc" "$B/reference/.removed-aidlc-$task-$arm${SUFFIX:-}"
      printf '@AGENTS.md\n' > "$d/CLAUDE.md"
    fi
    cp "$C/reference/task-$task.md" "$d/TASK.md"
    git -C "$d" init -q
    git -C "$d" config user.name "bakeoff"
    git -C "$d" config user.email "bakeoff@localhost"
    git -C "$d" add -A
    git -C "$d" commit -q -m "base: $task ($arm arm)"
    echo "built $task-$arm ($(git -C "$d" ls-files | wc -l) files)"
  done
done
