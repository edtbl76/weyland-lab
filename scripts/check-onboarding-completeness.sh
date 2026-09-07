#!/usr/bin/env bash
# Onboarding-completeness guard (B154 Phase 1a — the paved-road placement check).
#
# WHY THIS EXISTS: onboarding a new service means wiring it into every estate surface by hand, and the
# surfaces drift. The coverage family already proves a service is SCRAPED (check-servicemonitor-coverage),
# VISUALIZED (dashboard), ALERTED (alert-coverage), CATALOGED (datahub-coverage) and REGISTERED
# (check-app-registry). NOTHING proved a deployed service is PLACED in the architecture model — and the
# DoD itself flags exactly this drift ("ten check-*.sh guards exist; none appear in the LikeC4 model").
# It bit firsthand 2026-09-07: the image-provenance CronJob was missing its LikeC4 node and only caught
# in a manual DoD re-audit. This closes that surface: every DEPLOYED service in the registry must resolve
# to a real element in the single LikeC4 model (docs/architecture/weyland.likec4).
#
# THE CONTRACT IS DECLARATIVE, NOT FUZZY. The registry (applications.yaml) declares `deployed: true|false`
# per service; a `deployed: true` service must be placed. Placement resolves by an explicit `likec4: <id>`
# on the entry (authoritative — use it for a subsumed/renamed element, e.g. dbt -> dagster) or, absent
# that, by a normalized match of the service key/name against the model's element ids/display names
# (kind-agnostic: component/gateway/store/node all count). A `deployed: true` service that resolves to
# nothing is drift — the guard tells you to add the element or declare `likec4:`.
#
#   usage: scripts/check-onboarding-completeness.sh [--list]
#          --list   print every deployed service and its resolved element, then exit 0
#
# EXIT CODES (the fail-closed contract the coverage guards share):
#   0  every deployed service is placed in the model
#   1  a deployed service is UNPLACED (named)
#   2  the guard could not do its job (registry/model unreadable, empty, or no elements parsed)
#
# INPUTS (fixtures for tests; a set env var overrides the default path):
#   REGISTRY_FILE   applications.yaml            (default: the platform registry)
#   LIKEC4_FILE     the LikeC4 model             (default: docs/architecture/weyland.likec4)
set -euo pipefail

if [ -r "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh" ]; then
  # shellcheck source=scripts/lib/common.sh
  . "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"
fi
PLATFORM_DIR="${PLATFORM_DIR:-}"
REPO_ROOT="${REPO_ROOT:-.}"
REGISTRY_FILE="${REGISTRY_FILE:-$PLATFORM_DIR/services/weyland-dagster/weyland_pipeline/applications.yaml}"
LIKEC4_FILE="${LIKEC4_FILE:-$REPO_ROOT/docs/architecture/weyland.likec4}"

LIST=0
case "${1:-}" in
  "") ;;
  --list) LIST=1 ;;
  *) echo "unknown arg: $1" >&2; exit 2 ;;
esac

python3 - "$REGISTRY_FILE" "$LIKEC4_FILE" "$LIST" <<'PY'
import sys, re, yaml
reg_f, lk_f, listmode = sys.argv[1], sys.argv[2], sys.argv[3] == "1"

try:
    d = yaml.safe_load(open(reg_f))
except Exception as e:
    print(f"CANNOT RUN — registry unreadable ({reg_f}): {str(e)[:120]}", file=sys.stderr); sys.exit(2)
apps = (d or {}).get("applications")
if not apps:
    print(f"CANNOT RUN — no `applications` in {reg_f} (read failed?) — refusing to report a clean estate", file=sys.stderr); sys.exit(2)
try:
    lk = open(lk_f).read()
except Exception as e:
    print(f"CANNOT RUN — LikeC4 model unreadable ({lk_f}): {str(e)[:120]}", file=sys.stderr); sys.exit(2)

# kind-agnostic element extraction: <id> = <anyKind> "Display name"
elems = dict(re.findall(r'^\s+([A-Za-z][A-Za-z0-9]*)\s*=\s*[A-Za-z][A-Za-z0-9]*\s+"([^"]+)"', lk, re.M))
if not elems:
    print(f"CANNOT RUN — no elements parsed from {lk_f} — refusing to report every service unplaced", file=sys.stderr); sys.exit(2)

def norm(s): return re.sub(r'[^a-z0-9]', '', (s or '').lower())
nid = {i: norm(i) for i in elems}
nnm = {i: norm(n) for i, n in elems.items()}

def resolve(app):
    ov = app.get("likec4")
    if ov:
        return (ov if ov in elems else None), ov
    k, n = norm(app["key"]), norm(app.get("name", app["key"]))
    hit = next((i for i in elems if k in (nid[i], nnm[i]) or n in (nid[i], nnm[i])), None)
    return hit, None

deployed = [a for a in apps if a.get("deployed") is True]
missing = []
for a in deployed:
    el, ov = resolve(a)
    if listmode:
        print(f"  {a['key']:28} -> {el or 'UNPLACED'}")
        continue
    if el is None:
        why = f"declared likec4:{ov} is not in the model" if ov else "no LikeC4 element matches its key or name"
        missing.append((a["key"], a.get("name"), why))

if listmode:
    sys.exit(0)
if missing:
    print(f"UNPLACED — {len(missing)} deployed service(s) are not in the LikeC4 model:", file=sys.stderr)
    for k, n, why in missing:
        print(f"  - {k} ({n}) — {why}", file=sys.stderr)
    print("Fix: add the element to docs/architecture/weyland.likec4, or set `likec4: <id>` on the registry entry.", file=sys.stderr)
    sys.exit(1)
print(f"OK — all {len(deployed)} deployed service(s) are placed in the LikeC4 model.")
sys.exit(0)
PY
