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
# THE FULL DoD §6 CHECKLIST — declare + account. Onboarding a service means clearing EVERY §6 gate, and
# CI can only file-check some of them. So each deployed service DECLARES which conditional gates apply
# (`metrics`, `ingress`), the guard VERIFIES the file-checkable gates, and ACCOUNTS the rest per service
# in a matrix (`--list`) — nothing is silently skipped.
#   VERIFIED here (hard-fail):
#     SCHEMA     every entry declares a boolean `deployed`; every deployed service also declares boolean
#                `metrics` + `ingress` — an undeclared conditional gate is an UNACCOUNTED gate (fail),
#                and a missing `deployed` would silently skip the whole service (the footgun this kills).
#     PORT       every deployed service declares a `port_component`.
#     PLACEMENT  every deployed service resolves to a real LikeC4 element.
#   ACCOUNTED (surfaced in the --list matrix, owned elsewhere — verified there, not re-checked here):
#     metrics→ServiceMonitor+dashboard  LIVE — servicemonitor-coverage + dashboard-coverage reconcile it
#                at runtime (a new metrics service with no ServiceMonitor shows up as `blind` there).
#     *Down alert                       LIVE — alert-coverage.
#     ingress→Kuma monitor              MANUAL — Kuma monitors are UI-configured, not in git.
#     logs→Loki                         AUTO — Alloy scrapes every pod's logs.
#     arch.md §6 row                    curated subset, no clean predicate — reviewed by hand at the gate.
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

# SCHEMA FIRST — the declaration must be COMPLETE, because the accounting below is only trustworthy if
# every deployed service has declared which conditional gates apply. A missing `deployed` would silently
# skip a service (the absent-reads-as-not-deployed footgun); a deployed service that never declared
# `metrics`/`ingress` means we cannot know whether it needs a ServiceMonitor or a Kuma monitor — an
# unaccounted gate. Both fail closed rather than pass by omission.
schema_bad = []
for a in apps:
    k = a.get("key", "<no-key>")
    if "deployed" not in a or a["deployed"] not in (True, False):
        schema_bad.append((k, "no boolean `deployed`")); continue
    if a["deployed"] is True:
        for fld in ("metrics", "ingress"):
            if fld not in a or a[fld] not in (True, False):
                schema_bad.append((k, f"deployed but no boolean `{fld}` (its DoD §6 gate can't be accounted)"))

deployed = [a for a in apps if a.get("deployed") is True]
no_port = [a["key"] for a in deployed if not a.get("port_component")]
unplaced = []
for a in deployed:
    el, ov = resolve(a)
    if el is None and not listmode:
        why = f"declared likec4:{ov} is not in the model" if ov else "no LikeC4 element matches its key or name"
        unplaced.append((a["key"], a.get("name"), why))

# --list = the comprehensive per-service DoD §6 onboarding matrix. Every gate for every deployed service
# is shown with its disposition: VERIFIED here, LIVE (owned by a named coverage guard that reconciles it
# at runtime, incl. for new services), MANUAL (not expressible in git — a human gate), AUTO (handled by
# platform default), or n/a. Nothing is silently skipped — that is what "onboarding-complete" means.
if listmode:
    print("# DoD §6 onboarding matrix — per deployed service")
    print(f"# {'service':26} {'placement':16} {'port':4} {'metrics':30} {'alert':22} {'kuma':16} logs / arch§6")
    for a in deployed:
        el, _ = resolve(a)
        m = "ServiceMonitor+dash: LIVE(sm/dash-cov)" if a.get("metrics") is True else "n/a (no /metrics)"
        km = "MANUAL (Kuma UI)" if a.get("ingress") is True else "n/a (no ingress)"
        print(f"  {a['key']:26} {(el or 'UNPLACED'):16} {('ok' if a.get('port_component') else 'MISS'):4} "
              f"{m:30} {'*Down: LIVE(alert-cov)':22} {km:16} AUTO(Alloy) / curated(n/a)")
    print("# VERIFIED-here: placement + port + declaration completeness. LIVE: servicemonitor-coverage /")
    print("# dashboard-coverage / alert-coverage reconcile these at runtime, new services included.")
    print("# MANUAL: Kuma monitors are UI-configured (not in git). AUTO: Alloy scrapes all pod logs to Loki.")
    print("# arch.md §6 is a curated subset (no clean predicate) — reviewed by hand at the DoD gate.")
    sys.exit(0)

problems = False
if schema_bad:
    problems = True
    print(f"SCHEMA — {len(schema_bad)} registry declaration(s) incomplete (an unaccounted gate is a silent gap):", file=sys.stderr)
    for k, why in schema_bad: print(f"  - {k}: {why}", file=sys.stderr)
if no_port:
    problems = True
    print(f"PORT — {len(no_port)} deployed service(s) declare no `port_component`:", file=sys.stderr)
    for k in no_port: print(f"  - {k}", file=sys.stderr)
if unplaced:
    problems = True
    print(f"UNPLACED — {len(unplaced)} deployed service(s) are not in the LikeC4 model:", file=sys.stderr)
    for k, n, why in unplaced: print(f"  - {k} ({n}) — {why}", file=sys.stderr)
    print("Fix: add the element to docs/architecture/weyland.likec4, or set `likec4: <id>` on the registry entry.", file=sys.stderr)
if problems:
    sys.exit(1)
n_metrics = sum(1 for a in deployed if a.get("metrics") is True)
n_ingress = sum(1 for a in deployed if a.get("ingress") is True)
print(f"OK — {len(deployed)} deployed service(s) onboarding-complete: all declare metrics/ingress, "
      f"have a Port component + LikeC4 placement. Conditional gates accounted "
      f"(metrics→ServiceMonitor/dashboard {n_metrics} LIVE, ingress→Kuma {n_ingress} MANUAL, alert LIVE, "
      f"logs AUTO, arch§6 curated). Run --list for the per-service matrix.")
sys.exit(0)
PY
