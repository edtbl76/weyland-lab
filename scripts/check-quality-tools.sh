#!/usr/bin/env bash
# Drift guard for the quality-suite registry. Repo-root quality-tools.yaml is the SOURCE OF TRUTH; this asserts the
# scan-suite tools it declares (runner: scan-suite, enabled: true) EXACTLY match what scan.py actually runs — so a
# tool added to one but not the other fails instead of silently drifting (the "9 vs 10" class of bug). Mirrors
# scripts/check-app-registry.sh. Run from anywhere; script is in the repo-root ./scripts.
set -euo pipefail
. "$(dirname "$0")/lib/common.sh"
here="$REPO_ROOT"
python3 - "$here/quality-tools.yaml" \
  "$PLATFORM_DIR/services/scan-suite/scan.py" <<'PY'
import sys, re, yaml
reg, scan = sys.argv[1], sys.argv[2]
declared = {t["id"] for t in yaml.safe_load(open(reg))["tools"]
            if t.get("runner") == "scan-suite" and t.get("enabled")}
src = open(scan).read()
posted = set(re.findall(r'post\("([^"]+)"', src))
if "post_hotspot" in src:
    posted.add("code-maat")   # code-maat posts hotspots (kind:hotspot), not a severity count
missing = declared - posted   # in the registry, but scan.py never runs it
extra = posted - declared     # scan.py runs it, but it's not in the registry
if missing or extra:
    if missing:
        print("MISSING from scan.py (declared scan-suite/enabled, not posted):", sorted(missing))
    if extra:
        print("EXTRA in scan.py (posted, not in registry):", sorted(extra))
    sys.exit(1)
print(f"OK — {len(declared)} scan-suite tools in quality-tools.yaml match scan.py exactly.")
PY
