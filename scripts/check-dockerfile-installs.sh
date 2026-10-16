#!/usr/bin/env bash
# Dockerfile direct-install ratchet (2026-10-16). A `pip install <pkg>` line in a Dockerfile is invisible to every
# source scanner (they read requirements files) and, unpinned, drifts on any rebuild — the class that took Dagster down
# on 2026-10-01; tool-server's mcp 1.28.1 hid in one through GHSA-84m7-p3x7-pcfv. The first count was 103 packages
# (23 pinned, 80 unpinned) across 14 Dockerfiles. Each Dockerfile has a ceiling in scripts/ci/dockerfile-installs.baseline
# that may only FALL: move installs into a pinned requirements file, then lower it with --write-baseline.
#
#   usage: scripts/check-dockerfile-installs.sh [--list | --write-baseline]
# EXIT: 0 every Dockerfile at or under its ceiling (one below it is named: lower the baseline) · 1 a count above its
#   ceiling, or a Dockerfile not in the baseline, named · 2 could not check (no Dockerfile found, baseline unreadable).
# Logic: scripts/lib/dockerfile_installs.py (tests: scripts/tests/test_dockerfile_installs.py). Runbook: code-quality.md.
set -euo pipefail
. "$(dirname "$0")/lib/common.sh"
BASELINE="${DOCKERFILE_INSTALLS_BASELINE:-$REPO_ROOT/scripts/ci/dockerfile-installs.baseline}"
ROOT="${DOCKERFILE_INSTALLS_ROOT:-$REPO_ROOT}"
MODE="${1:-check}"
case "$MODE" in check|--list|--write-baseline) ;; *) echo "usage: $0 [--list | --write-baseline]" >&2; exit 2 ;; esac

PYTHONPATH="$REPO_ROOT/scripts/lib" python3 - "$ROOT" "$BASELINE" "$MODE" <<'PY'
import glob, os, sys
import dockerfile_installs as d
root, baseline_path, mode = sys.argv[1:]
files = sorted(p for p in glob.glob(os.path.join(root, "nodes", "**", "Dockerfile*"), recursive=True)
               if os.path.isfile(p))
if not files:
    print(f"CANNOT CHECK: no Dockerfile under {root}/nodes — refusing to report a clean tree", file=sys.stderr)
    sys.exit(2)
counts = {}
for p in files:
    with open(p, encoding="utf-8", errors="replace") as f:
        counts[os.path.relpath(p, root)] = len(d.packages(f.read()))
used = sum(1 for n in counts.values() if n)
if mode == "--write-baseline":
    d.write_baseline(baseline_path, counts)
    print(f"baseline written: {sum(counts.values())} direct install(s) across {used} Dockerfile(s)")
    sys.exit(0)
if mode == "--list":
    for p, n in sorted(counts.items()):
        if n:
            print(f"  {n:3d}  {p}")
try:
    baseline = d.read_baseline(baseline_path)
except (OSError, ValueError) as e:
    print(f"CANNOT CHECK: baseline {baseline_path} unreadable: {e}", file=sys.stderr)
    sys.exit(2)
bad, lower = d.compare(counts, baseline)
for b in bad:
    print(f"  FAIL {b}")
for low in lower:
    print(f"  LOWER THE BASELINE: {low} (scripts/check-dockerfile-installs.sh --write-baseline)")
if bad:
    print(f"DOCKERFILE INSTALLS ABOVE THE RATCHET: {len(bad)} file(s). Move them into a pinned requirements file.")
    sys.exit(1)
print(f"OK — {sum(counts.values())} direct pip install(s) across {used} Dockerfile(s), none above its ceiling.")
PY
