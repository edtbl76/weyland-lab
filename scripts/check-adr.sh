#!/usr/bin/env bash
# check-adr.sh — repo guard for the Architecture Decision Record log (B248, CI repo-guards).
#
# The log is docs/adr/: MADR files named NNNN-slug.md, written with the zircote-plugins/adr Claude Code plugin
# (/adr:new, /adr:supersede) or by hand from its template — so every harness can add one. This guard is what keeps the
# log trustworthy whichever tool wrote the file:
#   1. every ADR has the required sections: Status, Context and Problem Statement, Considered Options (the
#      alternatives — the inception rule's "Alternatives Rejected"), Decision Outcome, Consequences;
#   2. its status is one of the workflow's (proposed, accepted, deprecated, rejected, superseded), and a
#      "Superseded by [ADR-NNNN](...)" names an ADR that exists;
#   3. the numbers run 0001.. with no gap and no duplicate;
#   4. README.md (the index) lists every ADR file, and no row points at a missing one.
#
# Usage: bash scripts/check-adr.sh           (ADR_DIR overrides docs/adr for tests)
# Exit:  0 valid · 1 a real defect · 2 could not run (no directory, no ADRs, no python3) — nothing is never a pass
set -uo pipefail
REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DIR="${ADR_DIR:-$REPO_ROOT/docs/adr}"

command -v python3 >/dev/null || { echo "check-adr: python3 not found" >&2; exit 2; }
[ -d "$DIR" ] || { echo "check-adr: no ADR directory at $DIR" >&2; exit 2; }

python3 - "$DIR" <<'PY'
import os, re, sys

d = sys.argv[1]
NAME = re.compile(r"^(\d{4})-[a-z0-9][a-z0-9-]*\.md$")
REQUIRED = [r"^## Status\s*$", r"^## Context and Problem Statement\s*$", r"^## Considered Options\s*$",
            r"^## Decision Outcome\s*$", r"^#{2,3} Consequences\s*$"]
LABEL = ["Status", "Context and Problem Statement", "Considered Options", "Decision Outcome", "Consequences"]
STATUSES = {"proposed", "accepted", "deprecated", "rejected", "superseded"}
SUPERSEDED = re.compile(r"^superseded by \[adr-(\d{4})\]", re.IGNORECASE)

files = sorted(f for f in os.listdir(d) if NAME.match(f))
if not files:
    print(f"check-adr: no ADRs in {d} (expected NNNN-slug.md files)", file=sys.stderr)
    sys.exit(2)

errors = []
numbers = {}
for f in files:
    numbers.setdefault(NAME.match(f).group(1), []).append(f)

for n, fs in sorted(numbers.items()):
    if len(fs) > 1:
        errors.append(f"duplicate number {n}: {', '.join(fs)}")
expected = [f"{i:04d}" for i in range(1, len(numbers) + 1)]
missing = [n for n in expected if n not in numbers]
if missing:
    errors.append(f"numbering must run 0001..{len(numbers):04d} with no gap; missing {', '.join(missing)}")

for f in files:
    text = open(os.path.join(d, f), encoding="utf-8").read()
    lines = text.splitlines()
    for pat, label in zip(REQUIRED, LABEL):
        if not any(re.match(pat, l) for l in lines):
            errors.append(f"{f}: missing required section '{label}'")
    try:
        i = next(k for k, l in enumerate(lines) if re.match(REQUIRED[0], l))
        status = next(l.strip() for l in lines[i + 1:] if l.strip())
    except StopIteration:
        continue
    m = SUPERSEDED.match(status)
    if m:
        if m.group(1) not in numbers:
            errors.append(f"{f}: status says Superseded by ADR-{m.group(1)}, which does not exist")
    elif status.lower() not in STATUSES:
        errors.append(f"{f}: status '{status}' is not one of {', '.join(sorted(STATUSES))} or 'Superseded by [ADR-NNNN](...)'")

readme = os.path.join(d, "README.md")
if not os.path.isfile(readme):
    errors.append("README.md (the ADR index) is missing")
else:
    linked = set(re.findall(r"\]\(\./(\d{4}-[a-z0-9-]+\.md)\)", open(readme, encoding="utf-8").read()))
    for f in files:
        if f not in linked:
            errors.append(f"README.md does not list {f}")
    for f in sorted(linked - set(files)):
        errors.append(f"README.md links {f}, which does not exist")

if errors:
    print("adr: the decision log has defects:", file=sys.stderr)
    for e in errors:
        print(f"  {e}", file=sys.stderr)
    sys.exit(1)
print(f"adr: {len(files)} ADR(s) valid in {d}")
PY
