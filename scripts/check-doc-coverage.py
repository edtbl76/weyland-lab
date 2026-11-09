#!/usr/bin/env python3
"""Doc-coverage guard (B239): every deployed app in the registry has a runbook and appears on a map.

  usage: check-doc-coverage.py [--root DIR]

Exit 0 covered (known gaps, `runbook: null` + `runbook_gap:`, are listed but pass); 1 a gap that is not recorded
(a missing runbook field or file, or an app on no map); 2 could not run (no registry). Runbook:
docs/definition-of-done.md (Pillars 1 and 2); the registry is
nodes/mother/lab/weyland-platform/services/weyland-dagster/weyland_pipeline/applications.yaml.
"""
import argparse
import os
import sys
from pathlib import Path

import yaml

sys.path.insert(0, os.path.join(os.path.dirname(os.path.abspath(__file__)), "lib"))
import doc_coverage as dc  # noqa: E402

REPO = Path(__file__).resolve().parents[1]
REGISTRY = "nodes/mother/lab/weyland-platform/services/weyland-dagster/weyland_pipeline/applications.yaml"


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--root", type=Path, default=REPO)
    a = ap.parse_args()
    reg_path = a.root / REGISTRY
    if not reg_path.is_file():
        print(f"doc-coverage: no registry at {reg_path}", file=sys.stderr)
        return 2
    apps = (yaml.safe_load(reg_path.read_text()) or {}).get("applications") or []
    if not apps:
        print("doc-coverage: the registry lists no applications", file=sys.stderr)
        return 2
    res = dc.check(apps, a.root)
    if res.gaps:
        print(f"doc-coverage: {len(res.gaps)} known runbook gap(s), recorded in the registry:")
        print("\n".join(f"  - {g}" for g in res.gaps))
    if res.errors:
        print(f"doc-coverage: FAIL, {len(res.errors)} unrecorded gap(s):")
        print("\n".join(f"  - {e}" for e in res.errors))
        return 1
    print(f"doc-coverage: OK, {res.checked} deployed app(s) each have a runbook (or a recorded gap) and a map entry")
    return 0


if __name__ == "__main__":
    sys.exit(main())
