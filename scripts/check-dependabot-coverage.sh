#!/usr/bin/env bash
# check-dependabot-coverage.sh (B214, 2026-10-16) — every directory holding a requirements*.txt has a pip entry in
# .github/dependabot.yml.
#
# WHY THIS EXISTS: the config's own header says "every requirements.txt gets an explicit entry. An unlisted directory is
# an unwatched directory." On 2026-10-16 only 4 of the 23 directories with requirements files had one. B213 had just
# moved every Dockerfile `pip install` into lockfiles, 9 of them in unlisted directories, so an advisory against those
# pins could never reach a security PR. Nothing compared the config with the tree.
#
# EXCLUDED, with the reason: golden-paths/ (the per-language service templates; a service scaffolded from one lands in
# its own directory and needs its own entry) and tests/lang/ (test fixtures). Neither is deployed.
#
# EXIT: 0 = every requirements directory watched · 1 = an unwatched one, named · 2 = cannot check (no config, an
# unparseable one, or no requirements directory found). Checking nothing is never a pass.
# SEAMS: DEPENDABOT_ROOT (the tree), DEPENDABOT_CONFIG (the config file).
set -euo pipefail

ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DEPENDABOT_ROOT="${DEPENDABOT_ROOT:-$ROOT}"
DEPENDABOT_CONFIG="${DEPENDABOT_CONFIG:-$DEPENDABOT_ROOT/.github/dependabot.yml}"

command -v python3 >/dev/null 2>&1 || { echo "CANNOT CHECK: python3 not found on PATH" >&2; exit 2; }

DEPENDABOT_ROOT="$DEPENDABOT_ROOT" DEPENDABOT_CONFIG="$DEPENDABOT_CONFIG" python3 - <<'PY'
import os, sys

root, cfg = os.environ["DEPENDABOT_ROOT"], os.environ["DEPENDABOT_CONFIG"]
EXCLUDED = ("golden-paths/", "tests/lang/")
SKIP_DIRS = {".git", "node_modules", ".venv", "venv", "__pycache__", ".claude"}


def cannot(msg):
    print(f"CANNOT CHECK: {msg}")
    sys.exit(2)


try:
    import yaml
except ImportError:
    cannot("pyyaml is not installed")
try:
    doc = yaml.safe_load(open(cfg, encoding="utf-8"))
except FileNotFoundError:
    cannot(f"{cfg} does not exist")
except Exception as exc:
    cannot(f"{cfg} does not parse: {exc}")
if not isinstance(doc, dict) or not isinstance(doc.get("updates"), list):
    cannot(f"{cfg} has no `updates:` list")

watched = set()
for u in doc["updates"]:
    if not isinstance(u, dict) or u.get("package-ecosystem") != "pip":
        continue
    for d in [u.get("directory")] + list(u.get("directories") or []):
        if d:
            watched.add(d.strip("/"))

dirs = set()
for here, subdirs, files in os.walk(root):
    subdirs[:] = [s for s in subdirs if s not in SKIP_DIRS]
    if any(f.startswith("requirements") and f.endswith(".txt") for f in files):
        rel = os.path.relpath(here, root)
        rel = "" if rel == "." else rel
        if not (rel + "/").startswith(EXCLUDED):
            dirs.add(rel)
if not dirs:
    cannot(f"no directory under {root} holds a requirements*.txt")

unwatched = sorted(dirs - watched)
for d in unwatched:
    print(f"UNWATCHED: {d or '/'} has requirements files but no pip entry in .github/dependabot.yml")
if unwatched:
    print(f"{len(unwatched)} of {len(dirs)} requirements director{'y' if len(dirs) == 1 else 'ies'} unwatched: an "
          "advisory against their pins never reaches a security PR. Add a pip entry for each.")
    sys.exit(1)
print(f"OK — {len(dirs)} requirements director{'y' if len(dirs) == 1 else 'ies'} watched by Dependabot "
      f"(excluded: {', '.join(EXCLUDED)}).")
PY
