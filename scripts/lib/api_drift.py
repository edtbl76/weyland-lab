#!/usr/bin/env python3
"""Live API drift check (B155) — the runtime half of API lifecycle governance.

For every catalogued API that has both a captured contract snapshot (`spec`) and a way to fetch its
live contract (`spec_source`), this fetches the LIVE spec and diffs it against the committed snapshot
with the breaking-change engine (api_spec_diff). It catches a deployed API that DRIFTED from its
governed contract — a route removed, a field dropped, a new required field — without the catalog +
snapshot being updated and the version bumped.

Runs in-cluster as the `api-drift` CronJob (the .svc / *.weyland.lab spec_sources resolve there). Also
runnable on-demand wherever the sources are reachable.

FAIL-CLOSED, but honest about reachability: a source that cannot be fetched (a scaled-to-zero service,
a down pod) is SKIPPED and reported as unreachable — that is not drift, and firing nightly on every
asleep service would be noise. A breaking DIFF between a reachable live spec and its snapshot is a real
defect → exit 1. Cannot read the catalog/snapshots at all → exit 2.

  usage: api_drift.py <apis.yaml> <specs_dir>
  exit:  0 = no breaking drift (some sources may be skipped-unreachable, listed)
         1 = breaking drift on a reachable API (named)
         2 = could not run (catalog/specs unreadable)

  A spec_source of http(s):// is fetched over HTTP; anything else is treated as a local file path
  (used by the tests to feed a 'live' spec without a network).
"""
import json
import os
import sys
import urllib.request

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import api_spec_diff  # noqa: E402

try:
    import yaml
except ImportError:
    yaml = None


def _load_catalog(path):
    text = open(path).read()
    if yaml is not None:
        return (yaml.safe_load(text) or {}).get("apis") or []
    # Minimal fallback if pyyaml is absent (the cron image installs it; this keeps the runner honest).
    raise RuntimeError("pyyaml required to read the API catalog")


def _fetch(source, timeout=8):
    if source.startswith("http://") or source.startswith("https://"):
        req = urllib.request.Request(source, headers={"Accept": "application/json"})
        with urllib.request.urlopen(req, timeout=timeout) as r:  # noqa: S310 (trusted in-cluster hosts)
            return json.loads(r.read().decode())
    with open(source) as fh:  # local path — test fixture
        return json.load(fh)


def main(argv):
    if len(argv) != 2:
        print(__doc__.strip().splitlines()[-6], file=sys.stderr)
        return 2
    apis_f, specs_dir = argv
    try:
        apis = _load_catalog(apis_f)
    except Exception as e:
        print(f"CANNOT RUN — catalog unreadable ({apis_f}): {str(e)[:120]}", file=sys.stderr)
        return 2
    if not apis:
        print(f"CANNOT RUN — no apis in {apis_f}", file=sys.stderr)
        return 2

    checked, skipped, breaking = [], [], []
    for a in apis:
        spec, source = a.get("spec"), a.get("spec_source")
        if not spec or not source:
            continue  # not a snapshot-backed API (mcp/openai-compat without a captured contract)
        snap_path = os.path.join(specs_dir, os.path.basename(spec))
        if not os.path.isfile(snap_path):
            print(f"CANNOT RUN — snapshot missing for {a.get('id')}: {snap_path}", file=sys.stderr)
            return 2
        try:
            live = _fetch(source)
        except Exception as e:
            skipped.append((a.get("id"), f"unreachable: {str(e)[:60]}"))
            continue
        snapshot = json.load(open(snap_path))
        changes = api_spec_diff.diff(snapshot, live)
        if changes is None:
            skipped.append((a.get("id"), "cannot compare (kind changed?)"))
            continue
        bad = [c for c in changes if c[0] == "BREAKING"]
        checked.append(a.get("id"))
        if bad:
            breaking.append((a.get("id"), a.get("version"), bad))

    for i, why in skipped:
        print(f"  SKIP {i}: {why}")
    if breaking:
        print(f"BREAKING DRIFT — {len(breaking)} API(s) diverged from their governed contract:", file=sys.stderr)
        for i, ver, bad in breaking:
            print(f"  - {i} (v{ver}):", file=sys.stderr)
            for sev, detail in bad:
                print(f"      {detail}", file=sys.stderr)
        print("Fix: re-capture the snapshot into docs/api/specs/, bump the MAJOR version in apis.yaml, "
              "and migrate consumers (or revert the API change).", file=sys.stderr)
        return 1
    print(f"OK — {len(checked)} reachable API(s) match their committed contract; {len(skipped)} skipped (unreachable).")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
