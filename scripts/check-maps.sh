#!/usr/bin/env bash
# Map drift guard (B189 Closing Gap, 2026-11-06). The HTML maps under docs/ are written by hand, so nothing
# regenerated them when the platform changed: on 2026-11-06 the CI map said "23-step" against a 70-step pipeline,
# and the Platform Map had no Slack, Grafana Cloud IRM or Trunk, all three live. DoD Pillar 2 checked diagrams
# (LikeC4, Mermaid), not maps, so B184, U14 and B189 each shipped without one. This guard gives the maps an owner.
#
# Checks:
#   1. every step in the pipeline (.woodpecker/*.yml, one file per workflow since B200) is named on docs/ci-architecture-map.html as a step card (class="name") or a
#      lane chip (class="n"). Prose mentions do not count: a step must be ON the map, not merely in a sentence.
#   2. the CI map's "<N>-step" claim equals the real count of DISTINCT step names (trunk-upload runs in several
#      workflows but is one step on the map).
#   3. every top-level LikeC4 external (`id = ext "…"`) has a row tagged data-c4="<id>" on docs/platform-map.html.
#
# EXIT: 0 clean · 1 drift (every miss named) · 2 could not check (a file missing, or nothing to check — an empty
# step list or model is never a pass).
#
# Test seams: CHECK_MAPS_PIPELINE, CHECK_MAPS_CI_MAP, CHECK_MAPS_LIKEC4, CHECK_MAPS_PLATFORM_MAP.
set -uo pipefail

. "$(dirname "$0")/lib/common.sh"
PIPELINE="${CHECK_MAPS_PIPELINE:-$REPO_ROOT/.woodpecker}"   # a directory of workflows, or one file (test seam)
CI_MAP="${CHECK_MAPS_CI_MAP:-$REPO_ROOT/docs/ci-architecture-map.html}"
LIKEC4="${CHECK_MAPS_LIKEC4:-$REPO_ROOT/docs/architecture/weyland.likec4}"
PLATFORM_MAP="${CHECK_MAPS_PLATFORM_MAP:-$REPO_ROOT/docs/platform-map.html}"

[ -e "$PIPELINE" ] || { echo "check-maps: $PIPELINE not found" >&2; exit 2; }
for f in "$CI_MAP" "$LIKEC4" "$PLATFORM_MAP"; do
  [ -f "$f" ] || { echo "check-maps: $f not found" >&2; exit 2; }
done
command -v python3 >/dev/null 2>&1 || { echo "check-maps: python3 not found on PATH" >&2; exit 2; }

PIPELINE_LIB="$REPO_ROOT/scripts/lib" python3 - "$PIPELINE" "$CI_MAP" "$LIKEC4" "$PLATFORM_MAP" <<'PY'
import os
import re
import sys

sys.path.insert(0, os.environ["PIPELINE_LIB"])
import woodpecker_pipeline as wp

pipeline, ci_map, likec4, platform_map = sys.argv[1:5]

try:
    names = list(dict.fromkeys(s["name"] for _, s in wp.steps(pipeline)))   # distinct, in pipeline order
except wp.PipelineError as exc:
    print(f"check-maps: {exc}", file=sys.stderr)
    sys.exit(2)
if not names:
    print(f"check-maps: no steps in {pipeline}", file=sys.stderr)
    sys.exit(2)

ci = open(ci_map).read()
problems = []
for n in names:
    entry = re.compile(r'class="(?:name|n)">' + re.escape(n) + "<")
    if not entry.search(ci):
        problems.append(f"CI map is missing step `{n}` (add a step card or lane chip to {ci_map})")

claim = re.search(r"(\d+)-step", ci)
if claim is None:
    problems.append(f"CI map states no '<N>-step' count (expected {len(names)})")
elif int(claim.group(1)) != len(names):
    problems.append(f"CI map says {claim.group(1)} steps; the pipeline has {len(names)}")

model = open(likec4).read()
exts = re.findall(r'^\s*(\w+)\s*=\s*ext\s+"', model, re.M)
if not exts:
    print(f"check-maps: no ext elements in {likec4}", file=sys.stderr)
    sys.exit(2)
platform = open(platform_map).read()
for e in exts:
    if f'data-c4="{e}"' not in platform:
        problems.append(f"Platform Map has no row for LikeC4 external `{e}` (add a row with data-c4=\"{e}\" to {platform_map})")

if problems:
    for p in problems:
        print(f"MAP DRIFT: {p}")
    print(f"{len(problems)} map problem(s). The maps are hand-written: update them in the same change.", file=sys.stderr)
    sys.exit(1)
print(f"OK — maps current: {len(names)} pipeline step(s) on the CI map, {len(exts)} external system(s) on the Platform Map.")
PY
