#!/usr/bin/env bash
# The AI-DLC 2.11.2 arm ("aidlc211"): trials/<task>-aidlc211[-r2|-r3]. Same base snapshot the aidlc (2.6.18) arm ran
# on, committed as-is, then upgraded the way upstream documents for a copy-channel project (guide 18, "Copy Channel"):
# the files AI-DLC owns under .claude/ are replaced by the verified 2.11.2 runtime (`cp -R runtime/claude/.`), the
# team's memory files (team.md, project.md) are kept, and the copy's own setup runs once
# (`aidlc.ts config --from <runtime> --harness claude --yes`). The upgrade is commit 2, "framework installed", like
# every other framework arm. Refuses to overwrite an existing trial dir.
#   runtime: upstream/aidlc-2.11.2/aidlc-copy-runtime-2.11.2.tar.gz, sha256 checked against the release's .sha256
set -euo pipefail
B="${SDD_BAKEOFF_HOME:-/home/edwardmangini/sdd-bakeoff}"   # work dir: trials, results, toolbox (outside the repo)
C="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"   # harness code: eval/sdd-bakeoff in the repo
RT="$B/upstream/aidlc-2.11.2/x/runtime"
T="$B/toolbox"
OWNED="agents aidlc-common hooks knowledge rules scopes sensors skills tools settings.json"
for task in ${TASKS:-small brown green vague}; do
  for rep in ${REPS:-r1 r2 r3}; do   # r1 = round 1 (no suffix), r2/r3 = replicates
    suf="-$rep"; [ "$rep" = r1 ] && suf=""
    id="$task-aidlc211$suf"; d="$B/trials/$id"
    [ -e "$d" ] && { echo "exists, skipping: $d"; continue; }
    mkdir -p "$d"
    tar -xf "$B/reference/base-$task.tar" -C "$d"
    if [ "$task" = green ]; then
      mv "$d/nodes/mother/lab/weyland-platform/services/store-scaler" "$B/reference/.removed-store-scaler-aidlc211$suf"
    fi
    cp "$C/reference/task-$task.md" "$d/TASK.md"
    git -C "$d" init -q
    git -C "$d" config user.name "bakeoff"
    git -C "$d" config user.email "bakeoff@localhost"
    git -C "$d" add -A
    git -C "$d" commit -q -m "base: $task (aidlc211 arm, AI-DLC 2.6.18 as shipped in the repo)"
    # the upgrade: AI-DLC-owned files out, the 2.11.2 runtime in, the copy's setup once
    mkdir -p "$B/reference/.removed-aidlc2618-$id"
    for f in $OWNED; do [ -e "$d/.claude/$f" ] && mv "$d/.claude/$f" "$B/reference/.removed-aidlc2618-$id/"; done
    cp -R "$RT/claude/." "$d/"
    (cd "$d" && env -i HOME="$HOME" PATH="$T/bin:/usr/bin:/bin" bun .claude/tools/aidlc.ts config --from "$RT" --harness claude --yes > "$B/reference/.removed-aidlc2618-$id/config.log" 2>&1) \
      || { echo "aidlc config FAILED for $id (see reference/.removed-aidlc2618-$id/config.log)"; exit 1; }
    git -C "$d" add -A
    git -C "$d" commit -q -m "framework installed: AI-DLC 2.11.2 (copy channel)"
    echo "built $id: $(cd "$d" && env -i HOME="$HOME" PATH="$T/bin:/usr/bin:/bin" bun .claude/tools/aidlc.ts version 2>&1 | head -1)"
  done
done
