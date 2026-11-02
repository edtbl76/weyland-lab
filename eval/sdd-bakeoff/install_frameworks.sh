#!/usr/bin/env bash
# Install each framework into its built trial repos with the framework's OWN installer, at the pinned version the
# bake-off used, then commit the install as commit 2 ("framework installed: <arm>"), so a later diff from that commit
# is what the trial authored. AI-DLC 2.6.18 is part of the base snapshot (no install); AI-DLC 2.11.2 has its own
# builder (build_aidlc211.sh). Skips a repo that already has commit 2.
#   usage: TASKS="small brown green vague" SUFFIXES="'' -r2 -r3" install_frameworks.sh   (defaults shown; '' = round 1)
# These download external code (npm, PyPI/uv, GitHub): ask the owner first, naming the package, version and destination.
set -euo pipefail
B="${SDD_BAKEOFF_HOME:-/home/edwardmangini/sdd-bakeoff}"   # work dir: trials, results, toolbox (outside the repo)
T="$B/toolbox"
export PATH="$T/bin:$PATH"   # node 24 (OpenSpec 1.16.0 needs >= 22.12), uv, bun
install_one() {  # install_one <arm> <trial dir>
  case "$1" in
    bmad)     npx --yes bmad-method@6.12.4 install --directory "$2" --modules bmm --tools claude-code --yes ;;
    openspec) npx --yes @fission-ai/openspec@1.16.0 init --tools claude --no-animation "$2" ;;
    speckit)  uvx --from git+https://github.com/github/spec-kit.git@v1.2.5 specify init "$2" --force --non-interactive --integration claude ;;
    *) echo "unknown arm $1"; return 2 ;;
  esac
}
for task in ${TASKS:-small brown green vague}; do
  for suf in ${SUFFIXES:-"" -r2 -r3}; do
    [ "$suf" = "''" ] && suf=""
    for arm in bmad openspec speckit; do
      d="$B/trials/$task-$arm$suf"
      [ -d "$d" ] || { echo "no trial repo $d (run build_trials.sh first)"; exit 2; }
      [ "$(git -C "$d" rev-list --count HEAD)" -ge 2 ] && { echo "already installed: $task-$arm$suf"; continue; }
      install_one "$arm" "$d" > "$d.install.log" 2>&1 || { echo "install FAILED: $task-$arm$suf (see $d.install.log)"; exit 1; }
      git -C "$d" add -A
      git -C "$d" commit -q -m "framework installed: $arm"
      echo "installed $arm into $task-$arm$suf"
    done
  done
done
