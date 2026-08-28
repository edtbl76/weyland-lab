#!/usr/bin/env bash
# Drift guard for the quality-suite registry. Repo-root quality-tools.yaml is the SOURCE OF TRUTH.
#
# It asserts, for BOTH execution runners, that the registry and the implementation agree exactly —
# so a tool added to one but not the other FAILS instead of silently drifting (the "9 vs 10" class
# of bug this file was written for):
#
#   runner: scan-suite  ->  must be post()ed by services/scan-suite/scan.py
#   runner: lang-scan   ->  must be run_tool'd by scripts/run-lang-scan.sh
#
# WHY TWO RUNNERS (B88). The scan-suite is ONE image already carrying python + a full Go toolchain +
# a JRE. The Rust, Java and Node scanners need whole toolchains of their own, and bolting them on
# would roughly triple it — oversized layers have already broken builds here with
# `unpigz: invalid deflate` (memory buildkit-large-layer-corruption). Those tools run in per-language
# lanes with pinned images instead, mirroring the B88 test lanes. Adding a second runner without
# extending this guard would have reintroduced the exact drift the guard exists to stop, through a
# new door: 13 tools declared and nothing checking they were ever wired.
#
# Other runners (sonarqube, github-app, cli-gateway, ide) are external surfaces with no in-repo
# implementation to diff against, so they are declared but not enforced here.
#
# Run from anywhere; script is in the repo-root ./scripts.
set -euo pipefail
. "$(dirname "$0")/lib/common.sh"
here="$REPO_ROOT"

# Paths are overridable so the bats suite can drive the guard against fixtures rather than the real
# tree — a guard whose failure path is never exercised is not a guard.
REG="${WEYLAND_QT_REGISTRY:-$here/quality-tools.yaml}"
SCAN="${WEYLAND_QT_SCAN:-$PLATFORM_DIR/services/scan-suite/scan.py}"
LANGSCAN="${WEYLAND_QT_LANGSCAN:-$here/scripts/run-lang-scan.sh}"

python3 - "$REG" "$SCAN" "$LANGSCAN" <<'PY'
import sys, re, yaml

reg, scan, langscan = sys.argv[1], sys.argv[2], sys.argv[3]
tools = yaml.safe_load(open(reg))["tools"]


def declared(runner):
    return {t["id"] for t in tools if t.get("runner") == runner and t.get("enabled")}


def report(label, declared_ids, found_ids):
    """Returns True on drift. Prints BOTH directions — a tool that runs but is undeclared is just as
    much drift as one declared that never runs, and only naming one of them would half-fix it."""
    missing = declared_ids - found_ids
    extra = found_ids - declared_ids
    if missing:
        print(f"MISSING from {label} (declared enabled, never runs):", sorted(missing))
    if extra:
        print(f"EXTRA in {label} (runs, not in registry):", sorted(extra))
    return bool(missing or extra)

# ── scan-suite: tools are post()ed by scan.py ────────────────────────────────────────────────────
src = open(scan).read()
posted = set(re.findall(r'post\("([^"]+)"', src))
if "post_hotspot" in src:
    posted.add("code-maat")   # code-maat posts hotspots (kind:hotspot), not a severity count
ss_declared = declared("scan-suite")
drift = report("scan.py", ss_declared, posted)

# ── lang-scan: tools are invoked as `run_tool <id>` by run-lang-scan.sh ──────────────────────────
try:
    lsrc = open(langscan).read()
except FileNotFoundError:
    print(f"MISSING: {langscan} does not exist, but the registry declares lang-scan tools:",
          sorted(declared("lang-scan")))
    sys.exit(1)
wired = set(re.findall(r'run_tool\s+([A-Za-z0-9._-]+)', lsrc))
ls_declared = declared("lang-scan")
drift = report("run-lang-scan.sh", ls_declared, wired) or drift

if drift:
    sys.exit(1)
print(f"OK — {len(ss_declared)} scan-suite tools match scan.py, "
      f"{len(ls_declared)} lang-scan tools match run-lang-scan.sh.")
PY
