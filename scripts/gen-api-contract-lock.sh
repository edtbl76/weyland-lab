#!/usr/bin/env bash
# Regenerate the API contract lock (docs/api/specs/contract-lock.json) — the PR-time enforcement arm of
# API lifecycle (B155). The lock records, per snapshot-backed API, the APPROVED baseline: its exact
# contract + the version it was approved at. check-api-lifecycle.sh (CI) requires the lock to be current
# (each snapshot equals its locked baseline and the versions agree), so a contract cannot change silently.
#
# THE RULE THIS ENFORCES: when a snapshot has changed vs its locked baseline, this diffs them with the
# breaking-change engine (api_spec_diff.py). If the change is BREAKING, it REFUSES to re-lock unless the
# API's MAJOR version was bumped in apis.yaml — so a breaking change to a published API cannot ship
# without a major bump + a deliberate re-lock. Additive changes re-lock freely (minor/patch).
#
# Git-independent by design (the baseline lives IN the lock, not in git history), so it is robust in CI
# and locally alike. Run it after (re-)capturing a snapshot; commit the updated lock with the change.
#
#   usage: scripts/gen-api-contract-lock.sh
#   exit:  0 = lock written   1 = refused (a breaking change without a major bump — named)   2 = cannot run
set -euo pipefail
# API_LOCK_ROOT lets the tests point the generator at a temp tree (apis.yaml + docs/api/specs/ + lock).
here="${API_LOCK_ROOT:-$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)}"

python3 - "$here" <<'PY' || exit $?
import json, os, sys
root = sys.argv[1]
sys.path.insert(0, os.path.join(root, "scripts", "lib"))
import api_spec_diff  # noqa: E402
try:
    import yaml
except ImportError:
    print("CANNOT RUN — pyyaml required", file=sys.stderr); sys.exit(2)

apis_f = os.path.join(root, "nodes/mother/lab/weyland-platform/services/weyland-dagster/weyland_pipeline/apis.yaml")
lock_f = os.path.join(root, "docs/api/specs/contract-lock.json")
apis = (yaml.safe_load(open(apis_f)) or {}).get("apis") or []
old_lock = json.load(open(lock_f)) if os.path.isfile(lock_f) else {}

def major(v):
    try:
        return int(str(v).split(".")[0])
    except Exception:
        return 0

new_lock, refusals = {}, []
for a in apis:
    spec = a.get("spec")
    if not spec:
        continue  # only snapshot-backed (openapi/a2a) APIs are locked
    i, ver = a.get("id"), a.get("version")
    path = os.path.join(root, spec)
    if not os.path.isfile(path):
        print(f"CANNOT RUN — snapshot missing for {i}: {spec}", file=sys.stderr); sys.exit(2)
    current = json.load(open(path))
    prev = (old_lock.get(i) or {}).get("spec")
    if prev is not None and json.dumps(prev, sort_keys=True) != json.dumps(current, sort_keys=True):
        changes = api_spec_diff.diff(prev, current) or []
        breaking = [c for c in changes if c[0] == "BREAKING"]
        if breaking and major(ver) <= major((old_lock.get(i) or {}).get("version")):
            refusals.append((i, ver, (old_lock[i] or {}).get("version"), breaking))
    new_lock[i] = {"version": ver, "spec": current}

if refusals:
    print("REFUSED — breaking contract change(s) without a MAJOR version bump:", file=sys.stderr)
    for i, ver, oldver, breaking in refusals:
        print(f"  - {i}: v{oldver} -> v{ver} is a MAJOR change but the version did not increase its major:", file=sys.stderr)
        for sev, detail in breaking:
            print(f"      {detail}", file=sys.stderr)
    print("Fix: bump the MAJOR version in apis.yaml (and migrate consumers), then re-run. Or revert the "
          "breaking change. An additive change needs only a minor/patch bump.", file=sys.stderr)
    sys.exit(1)

json.dump(new_lock, open(lock_f, "w"), indent=2, sort_keys=True)
print(f"locked {len(new_lock)} contract(s) into docs/api/specs/contract-lock.json")
PY
