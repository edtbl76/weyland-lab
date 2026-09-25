#!/usr/bin/env bash
# check-requirements-sync.sh — every exact `==` pin in a requirements.in must equal its requirements.txt pin.
#
# WHY THIS EXISTS: the pip-tools split (2026-07-19) made each service's requirements.in the human-maintained
# SOURCE and requirements.txt the pinned OUTPUT the Dockerfiles install. On 2026-09-25 genre-trainer's .in still
# pinned cryptography 48.0.1 / mlflow 3.14.0 / aiohttp 3.14.1 after main had remediated .txt to 50.0.0 / 3.15.1 /
# 3.14.3 by hand. Nothing installs the .in, so nothing noticed — but dependabot treats it as the pip-compile
# source, so every re-cut of weyland-lab #63 regenerated .txt from the stale pins and re-opened 4 CVEs. Only a
# Sourcery check stopped a merge. Fix: when you remediate a pin, edit BOTH files (or recompile from the .in).
#
# SCOPE: exact `==` pins only. Loose entries (`>=`, bare names) are pip-compile's job and are not compared.
# Names compare the way pip does (PEP 503: case-insensitive, runs of `-_.` equal).
#
# DISCOVERY: every requirements.in under nodes/ (override the root with REQ_ROOT — the bats seam).
# EXIT: 0 = in sync · 1 = an .in pin disagrees with / is missing from its .txt · 2 = guard broken (no .in files
# found, or an .in with no sibling requirements.txt). Checking nothing is never a pass.
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
REQ_ROOT="${REQ_ROOT:-$ROOT/nodes}"

command -v python3 >/dev/null 2>&1 || { echo "❌ guard broken: python3 not found on PATH" >&2; exit 2; }

REQ_ROOT="$REQ_ROOT" ROOT="$ROOT" python3 - <<'PY'
import os, re, sys

root, repo = os.environ["REQ_ROOT"], os.environ["ROOT"]

def broken(msg):
    print(f"❌ guard broken: {msg}", file=sys.stderr); sys.exit(2)

def norm(name):
    return re.sub(r"[-_.]+", "-", name).lower()

# `name[extras] == version` at the start of a line; markers (`;`), comments and hash lines are ignored.
PIN = re.compile(r"^\s*([A-Za-z0-9][A-Za-z0-9._-]*)(?:\[[^\]]*\])?\s*==\s*([^\s;#\\]+)")

def exact_pins(path):
    pins = {}
    with open(path, encoding="utf-8") as f:
        for line in f:
            m = PIN.match(line)
            if m:
                pins[norm(m.group(1))] = (m.group(1), m.group(2))
    return pins

ins = []
for d, subdirs, files in os.walk(root):
    subdirs[:] = [s for s in subdirs if s not in (".git", "node_modules", ".venv", "venv", "__pycache__")]
    if "requirements.in" in files:
        ins.append(os.path.join(d, "requirements.in"))
ins.sort()
if not ins:
    broken(f"no requirements.in files found under {root}")

drift = []
for p in ins:
    rel = os.path.relpath(p, repo) if p.startswith(repo) else os.path.relpath(p, root)
    txt = os.path.join(os.path.dirname(p), "requirements.txt")
    if not os.path.isfile(txt):
        broken(f"{rel} has no sibling requirements.txt to compare against")
    want, have = exact_pins(p), exact_pins(txt)
    bad = []
    for key, (name, ver) in sorted(want.items()):
        got = have.get(key)
        if got is None:
            bad.append(f"{name}: .in=={ver}, absent from requirements.txt")
        elif got[1] != ver:
            bad.append(f"{name}: .in=={ver}  requirements.txt=={got[1]}")
    if bad:
        drift.append((rel, bad))
        print(f"  ❌ {rel}")
        for b in bad:
            print(f"       {b}")
    else:
        print(f"  ✓ {rel} ({len(want)} exact pin(s))")

if drift:
    print("", file=sys.stderr)
    print("❌ requirements.in pins disagree with requirements.txt. dependabot compiles FROM the .in, so a stale "
          "pin there regenerates a downgrade on every re-cut. Update the .in to the .txt version (or recompile).",
          file=sys.stderr)
    sys.exit(1)
print(f"OK — {len(ins)} requirements.in file(s): every exact pin matches its requirements.txt.")
PY
