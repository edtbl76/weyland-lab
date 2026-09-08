#!/usr/bin/env bash
# API lifecycle governance guard (B155 — the standing gate over apis.yaml).
#
# WHY THIS EXISTS: the estate had a human API inventory (docs/api.md) but no lifecycle governance —
# nothing said who owns an API, what version it is, whether it is published/deprecated/retired, or caught
# a breaking change. B12 (a static registry) was cancelled for exactly this gap. This guard governs the
# machine-readable catalog (apis.yaml) across the whole lifecycle: design → published → deprecated →
# retired. The breaking-change half is the engine (scripts/lib/api_spec_diff.py), run live by the
# api-drift CronJob against the committed contract snapshots (docs/api/specs/).
#
# CHECKS (all file-based, fail-closed):
#   SCHEMA       every API declares id + owner + kind + status + version (kind/status from the vocabularies)
#   OWNER        `owner` resolves to a real applications.yaml service (component or excluded)
#   SPEC         a PUBLISHED openapi/a2a API carries a `spec` snapshot that exists on disk (its contract
#                is captured + diffable) — a published typed contract with no snapshot is a governance hole
#   DEPRECATION  status: deprecated ⇒ deprecation.retire_by (a date) + deprecation.successor (an api id)
#   RETIRED      status: retired ⇒ no consumers (nothing may still call a retired API)
#   LOCK         the contract lock is current — each snapshot equals its approved baseline + version
#                (docs/api/specs/contract-lock.json). Re-locking refuses a breaking change that skipped a
#                MAJOR bump, so this is the PR-time breaking-change enforcement (complements the drift cron).
#
#   usage: scripts/check-api-lifecycle.sh [--list]
#          --list   print every API + its lifecycle status, then exit 0
#
# EXIT CODES: 0 = every API is well-governed; 1 = a governance defect (named); 2 = the guard could not
# run (catalog/registry unreadable or empty) — never conflated with a clean estate.
#
# INPUTS (fixtures; a set env var overrides the default path):
#   APIS_FILE      apis.yaml           (default: the platform API catalog)
#   REGISTRY_FILE  applications.yaml   (default: the platform service registry, for owner resolution)
#   SPECS_DIR      contract snapshots  (default: docs/api/specs)
set -euo pipefail

if [ -r "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh" ]; then
  # shellcheck source=scripts/lib/common.sh
  . "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
fi
PLATFORM_DIR="${PLATFORM_DIR:-}"
REPO_ROOT="${REPO_ROOT:-.}"
APIS_FILE="${APIS_FILE:-$PLATFORM_DIR/services/weyland-dagster/weyland_pipeline/apis.yaml}"
REGISTRY_FILE="${REGISTRY_FILE:-$PLATFORM_DIR/services/weyland-dagster/weyland_pipeline/applications.yaml}"
SPECS_DIR="${SPECS_DIR:-$REPO_ROOT/docs/api/specs}"

LIST=0
case "${1:-}" in
  "") ;;
  --list) LIST=1 ;;
  *) echo "unknown arg: $1" >&2; exit 2 ;;
esac

APIS_FILE="$APIS_FILE" REGISTRY_FILE="$REGISTRY_FILE" SPECS_DIR="$SPECS_DIR" REPO_ROOT="$REPO_ROOT" LIST="$LIST" python3 <<'PY'
import json, os, sys, yaml

apis_f, reg_f, specs_dir, listmode = (os.environ["APIS_FILE"], os.environ["REGISTRY_FILE"],
                                      os.environ["SPECS_DIR"], os.environ["LIST"] == "1")
try:
    apis = (yaml.safe_load(open(apis_f)) or {}).get("apis")
except Exception as e:
    print(f"CANNOT RUN — API catalog unreadable ({apis_f}): {str(e)[:120]}", file=sys.stderr); sys.exit(2)
if not apis:
    print(f"CANNOT RUN — no `apis` in {apis_f} — refusing to report a clean estate", file=sys.stderr); sys.exit(2)
try:
    reg = yaml.safe_load(open(reg_f)) or {}
except Exception as e:
    print(f"CANNOT RUN — service registry unreadable ({reg_f}): {str(e)[:120]}", file=sys.stderr); sys.exit(2)
services = {a["key"] for a in (reg.get("applications") or [])} | {e["key"] for e in (reg.get("excluded") or [])}
if not services:
    print(f"CANNOT RUN — no services parsed from {reg_f}", file=sys.stderr); sys.exit(2)

KINDS = {"openapi", "a2a", "mcp", "openai-compat", "raw-http"}
STATUSES = {"design", "published", "deprecated", "retired"}
ids = {a.get("id") for a in apis}

# `spec` is written repo-relative (docs/api/specs/<id>.json); resolve it by basename against SPECS_DIR,
# which is overridable for tests (unlike REPO_ROOT, which common.sh forces to the real repo root).

schema, owner_bad, spec_bad, dep_bad, retired_bad = [], [], [], [], []
for a in apis:
    i = a.get("id", "<no-id>")
    for fld in ("id", "owner", "kind", "status", "version"):
        if not a.get(fld):
            schema.append(f"{i}: missing `{fld}`")
    if a.get("kind") and a["kind"] not in KINDS:
        schema.append(f"{i}: invalid kind '{a['kind']}'")
    if a.get("status") and a["status"] not in STATUSES:
        schema.append(f"{i}: invalid status '{a['status']}'")
    if a.get("owner") and a["owner"] not in services:
        owner_bad.append(f"{i}: owner '{a['owner']}' is not a service in applications.yaml")
    if a.get("status") == "published" and a.get("kind") in ("openapi", "a2a"):
        spec = a.get("spec")
        if not spec:
            spec_bad.append(f"{i}: published {a['kind']} API has no `spec` snapshot (contract not captured)")
        elif not os.path.isfile(os.path.join(specs_dir, os.path.basename(spec))):
            spec_bad.append(f"{i}: `spec` snapshot missing on disk: {spec}")
    if a.get("status") == "deprecated":
        dep = a.get("deprecation") or {}
        if not dep.get("retire_by"):
            dep_bad.append(f"{i}: deprecated but no deprecation.retire_by date")
        succ = dep.get("successor")
        if not succ:
            dep_bad.append(f"{i}: deprecated but no deprecation.successor")
        elif succ not in ids:
            dep_bad.append(f"{i}: deprecation.successor '{succ}' is not a known API id")
    if a.get("status") == "retired" and (a.get("consumers") or []):
        retired_bad.append(f"{i}: retired but still has consumers {a.get('consumers')}")

# LOCK — the contract lock (docs/api/specs/contract-lock.json) is the PR-time breaking-change arm: it
# records each snapshot-backed API's APPROVED baseline + version. This asserts the lock is CURRENT — the
# snapshot equals its locked baseline and the versions agree. A drift means the contract or version
# changed without re-locking, and re-locking (gen-api-contract-lock.sh) REFUSES a breaking change that
# skipped a major bump — so a silent breaking change cannot pass here.
lock_bad = []
lock_path = os.path.join(specs_dir, "contract-lock.json")
lock = json.load(open(lock_path)) if os.path.isfile(lock_path) else None
for a in apis:
    spec = a.get("spec")
    if not spec:
        continue
    i = a.get("id")
    snap_path = os.path.join(specs_dir, os.path.basename(spec))
    if not os.path.isfile(snap_path):
        continue  # already reported by the SPEC check
    if lock is None:
        lock_bad.append(f"{i}: no contract lock exists — run scripts/gen-api-contract-lock.sh")
        continue
    entry = lock.get(i)
    if not entry:
        lock_bad.append(f"{i}: not in the contract lock — run scripts/gen-api-contract-lock.sh")
        continue
    current = json.load(open(snap_path))
    if json.dumps(current, sort_keys=True) != json.dumps(entry.get("spec"), sort_keys=True):
        lock_bad.append(f"{i}: snapshot changed vs the locked baseline — re-lock (gen-api-contract-lock.sh, "
                        "which refuses a breaking change without a major bump)")
    elif str(entry.get("version")) != str(a.get("version")):
        lock_bad.append(f"{i}: version '{a.get('version')}' != locked version '{entry.get('version')}' — re-lock")

if listmode:
    print(f"# API lifecycle catalog — {len(apis)} API(s)")
    print(f"# {'id':26} {'owner':20} {'kind':14} {'status':10} version  spec")
    for a in sorted(apis, key=lambda x: (x.get("status", ""), x.get("id", ""))):
        print(f"  {a.get('id',''):26} {a.get('owner',''):20} {a.get('kind',''):14} "
              f"{a.get('status',''):10} {str(a.get('version','')):8} {'yes' if a.get('spec') else '-'}")
    sys.exit(0)

problems = False
for label, rows, fix in [
    ("SCHEMA", schema, "declare id/owner/kind/status/version (kind∈openapi|a2a|mcp|openai-compat|raw-http)"),
    ("OWNER", owner_bad, "set `owner` to a real applications.yaml service key"),
    ("SPEC", spec_bad, "capture the contract into docs/api/specs/ and point `spec:` at it"),
    ("DEPRECATION", dep_bad, "a deprecated API needs deprecation.retire_by + deprecation.successor"),
    ("RETIRED", retired_bad, "a retired API must have no consumers — migrate them first"),
    ("LOCK", lock_bad, "run scripts/gen-api-contract-lock.sh after (re-)capturing a snapshot — it enforces the major-bump-on-breaking rule"),
]:
    if rows:
        problems = True
        print(f"{label} — {len(rows)} API(s):", file=sys.stderr)
        for r in rows:
            print(f"  - {r}", file=sys.stderr)
        print(f"  fix: {fix}", file=sys.stderr)

if problems:
    sys.exit(1)
pub = sum(1 for a in apis if a.get("status") == "published")
snap = sum(1 for a in apis if a.get("spec"))
print(f"OK — {len(apis)} API(s) well-governed: all declare owner/kind/status/version, owners resolve, "
      f"every published typed contract is snapshotted + locked ({snap} snapshots), deprecations + "
      f"retirements consistent. ({pub} published) Breaking changes enforced at PR time by the contract "
      f"lock (major-bump-on-breaking) + live by the api-drift cron.")
sys.exit(0)
PY
