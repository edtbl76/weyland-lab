#!/usr/bin/env bash
# Port IaC coverage guard (B137).
#
# WHY THIS EXISTS: `docs/runbooks/port.md` claims the B60 split keeps Port's SCHEMA in OpenTofu.
# On 2026-08-22 that claim was false and nothing noticed: 51 blueprints live / 13 in code, 8
# scorecards live / 0 in code, 4 integrations live / 0 in code. The gap opened one UI click at a
# time over two months and was found by accident, from an unrelated reverse-engineering scan.
#
# A clean `tofu plan` cannot detect this. Plan compares the code to the RESOURCES TOFU KNOWS ABOUT;
# a blueprint created in the UI is invisible to it, so "no changes" and "half the catalog is
# unversioned" are the same output. This guard asks the opposite question -- what is LIVE that the
# code does not describe -- and it is the only thing that can catch the disease recurring.
#
#   usage: scripts/check-port-iac-coverage.sh [--list]
#          --list   print the full live-vs-code table and exit 0 (no assertions)
#
# INPUTS. By default it authenticates to api.port.io with the credentials in
# nodes/mother/lab/weyland-platform/tofu/port/.env (gitignored) or the environment. To run it
# offline -- and to make it testable -- point these at snapshot files instead:
#
#   PORT_LIVE_BLUEPRINTS_JSON     GET /v1/blueprints
#   PORT_LIVE_SCORECARDS_JSON     GET /v1/scorecards
#   PORT_LIVE_INTEGRATIONS_JSON   GET /v1/integration
#   PORT_TF_DIR                   directory of .tf files (default: tofu/port)
#
# FAILS CLOSED. An unreachable API, an empty entity list, an unparseable .tf file, or a live set it
# cannot classify is a loud error -- never a skip and never an implicit pass. An absent result must
# not stand for a successful one; that class of bug has bitten this repo repeatedly, twice inside
# the very guard built to prevent it.
set -euo pipefail

. "$(dirname "${BASH_SOURCE[0]}")/lib/common.sh"

PORT_TF_DIR="${PORT_TF_DIR:-$PLATFORM_DIR/tofu/port}"
PORT_ENV_FILE="${PORT_ENV_FILE:-$PLATFORM_DIR/tofu/port/.env}"

# --- deliberately UI-managed, with the reason -------------------------------------------------
#
# B137's acceptance requires "a documented decision for anything deliberately left UI-managed (with
# the reason)". This IS that decision, in executable form: anything not listed here and not owned by
# a live integration must be in the code.
#
# The rule is: CODIFY WHAT CANNOT RECREATE ITSELF; DOCUMENT WHAT DOES.
#
# 1. Port SYSTEM blueprints (`_`-prefixed: _user, _team, _rule, ...). Port owns them, ships them with
#    every org, and the provider models them as a SEPARATE resource type (`port_system_blueprint`)
#    precisely because they are not ours to create or destroy. Codifying them buys nothing and hands
#    tofu a `destroy` it must never perform.
#
# 2. INTEGRATION-OWNED blueprints -- derived at runtime from the live integrations' own mappings, not
#    hardcoded, so installing a new integration does not make this guard lie. An Ocean integration
#    creates its blueprints on install (`arePortResourcesInitialized`) and REVISES them on upgrade:
#    github-ocean moved 6.8.1 -> 6.9.4 in two days here. If tofu owned `githubRepository`, every such
#    upgrade would show as drift and an apply would revert the integration's own schema. That is the
#    permanently-dirty plan this backlog item exists to cure, so codifying them would reintroduce the
#    disease in the name of curing it. They recreate themselves from the integration; that is the
#    documented reason.
#
# 3. The DORMANT list below: blueprints an integration created on install but does not currently map.
#    Same owner as (2), but they cannot be DERIVED from (2) because nothing maps them today -- so they
#    are named explicitly rather than silently tolerated.
DORMANT_UI_MANAGED=(
  "githubOrganization|created by github-ocean on install; not in the mapping (we ingest repos + PRs, not the org)"
  "githubUser|created by github-ocean on install; user ingestion is off (a solo lab has one user)"
  "githubWorkflow|created by github-ocean on install; CI lives in Woodpecker, not GitHub Actions"
  "githubWorkflowRun|created by github-ocean on install; see githubWorkflow"
)

# --- .tf parsing -------------------------------------------------------------------------------
#
# Parsed from the CODE, not from `tofu state`. State would answer "what does tofu know about", and
# a resource can sit in state with no code behind it -- which is exactly the condition B60's
# unexecuted `state rm` left the component entities in for weeks. The claim under test is that the
# CODE describes the live system, so the code is what gets read.

# tf_identifiers <resource-type> <dir> -- print the `identifier` of every resource of that type.
# For scorecards, prints `<blueprint>:<identifier>` since a scorecard id is unique only per blueprint.
tf_identifiers() {
  local rtype="$1" dir="$2"
  [ -d "$dir" ] || { echo "❌ not a directory: $dir" >&2; return 2; }
  python3 - "$rtype" "$dir" <<'PY'
import os, re, sys
rtype, d = sys.argv[1], sys.argv[2]
files = sorted(f for f in os.listdir(d) if f.endswith(".tf"))
if not files:
    print(f"no .tf files in {d}", file=sys.stderr); raise SystemExit(2)
head = re.compile(r'^resource\s+"%s"\s+"([^"]+)"\s*\{' % re.escape(rtype))
found = []
for fn in files:
    src = open(os.path.join(d, fn), encoding="utf-8").read().splitlines()
    i = 0
    while i < len(src):
        m = head.match(src[i])
        if not m:
            i += 1; continue
        # Walk the block by brace depth so a nested `identifier` (inside relations, a jsonencode
        # object, ...) can never be mistaken for the resource's own.
        depth, ident, blueprint = 1, None, None
        j = i + 1
        while j < len(src) and depth > 0:
            line = src[j]
            if depth == 1:
                a = re.match(r'\s*identifier\s*=\s*"([^"]+)"', line)
                if a and ident is None: ident = a.group(1)
                b = re.match(r'\s*blueprint\s*=\s*"([^"]+)"', line)
                if b and blueprint is None: blueprint = b.group(1)
                c = re.match(r'\s*installation_id\s*=\s*"([^"]+)"', line)
                if c and ident is None: ident = c.group(1)
            depth += line.count("{") - line.count("}")
            j += 1
        if ident is None:
            print(f"{fn}: resource {rtype}.{m.group(1)} has no literal identifier", file=sys.stderr)
            raise SystemExit(2)
        found.append(f"{blueprint}:{ident}" if rtype == "port_scorecard" else ident)
        i = j
print("\n".join(sorted(found)))
PY
}

# --- live-side readers -------------------------------------------------------------------------

# integration_owned_blueprints <integrations.json> -- every blueprint an integration's mapping writes.
integration_owned_blueprints() {
  python3 - "$1" <<'PY'
import json, sys
d = json.load(open(sys.argv[1], encoding="utf-8"))
igs = d.get("integrations")
if not igs:
    print("no integrations in the payload -- refusing to classify anything as integration-owned",
          file=sys.stderr)
    raise SystemExit(2)
out = set()
for i in igs:
    for r in ((i.get("config") or {}).get("resources") or []):
        mp = ((r.get("port") or {}).get("entity") or {}).get("mappings")
        for m in (mp if isinstance(mp, list) else [mp] if mp else []):
            bp = (m.get("blueprint") or "").strip('"')
            if bp: out.add(bp)
print("\n".join(sorted(out)))
PY
}

# live_identifiers <kind> <json> -- blueprint / scorecard / integration ids from a live payload.
live_identifiers() {
  python3 - "$1" "$2" <<'PY'
import json, sys
kind, path = sys.argv[1], sys.argv[2]
d = json.load(open(path, encoding="utf-8"))
if kind == "blueprint":
    items = d.get("blueprints"); out = [b["identifier"] for b in (items or [])]
elif kind == "scorecard":
    items = d.get("scorecards"); out = [f"{s['blueprint']}:{s['identifier']}" for s in (items or [])]
else:
    items = d.get("integrations"); out = [i["installationId"] for i in (items or [])]
if not items:
    print(f"live {kind} list is EMPTY -- an empty result is not a passing result", file=sys.stderr)
    raise SystemExit(2)
print("\n".join(sorted(out)))
PY
}

# dangling_relation_targets <blueprints.json> <codified-ids-file> -- relations declared by a CODIFIED
# blueprint whose target blueprint is NOT codified. Not a failure: it is the rebuild-order fact, and
# it must be visible rather than assumed.
dangling_relation_targets() {
  python3 - "$1" "$2" <<'PY'
import json, sys
live = {b["identifier"]: b for b in json.load(open(sys.argv[1], encoding="utf-8"))["blueprints"]}
coded = {l.strip() for l in open(sys.argv[2], encoding="utf-8") if l.strip()}
missing_live, out = [], []
for ident in sorted(coded):
    b = live.get(ident)
    if b is None:
        missing_live.append(ident); continue
    for rel, v in (b.get("relations") or {}).items():
        t = v.get("target")
        if t and t not in coded:
            out.append(f"{ident}.{rel} -> {t}")
if missing_live:
    print("codified but NOT LIVE: " + ", ".join(missing_live), file=sys.stderr)
    raise SystemExit(3)
print("\n".join(out))
PY
}

# --- live fetch --------------------------------------------------------------------------------

port_token() {
  # shellcheck source=/dev/null  # tofu/port/.env is gitignored; shellcheck can never follow it
  [ -f "$PORT_ENV_FILE" ] && { set -a; . "$PORT_ENV_FILE"; set +a; }
  : "${PORT_CLIENT_ID:?PORT_CLIENT_ID not set and not in $PORT_ENV_FILE}"
  : "${PORT_CLIENT_SECRET:?PORT_CLIENT_SECRET not set and not in $PORT_ENV_FILE}"
  local body tok
  # -sS not -sf: `curl -sf` collapses EVERY non-2xx to exit 0 with empty output, which is how three
  # separate gates in this repo reported success on an error. Read the body and require the field.
  body="$(curl -sS -X POST https://api.port.io/v1/auth/access_token \
    -H 'Content-Type: application/json' \
    -d "{\"clientId\":\"$PORT_CLIENT_ID\",\"clientSecret\":\"$PORT_CLIENT_SECRET\"}")" || {
      echo "❌ could not reach api.port.io for a token" >&2; return 1; }
  tok="$(printf '%s' "$body" | python3 -c 'import sys,json;print(json.load(sys.stdin).get("accessToken",""))' 2>/dev/null || true)"
  [ -n "$tok" ] || { echo "❌ Port returned no accessToken (check the credentials in $PORT_ENV_FILE)" >&2; return 1; }
  printf '%s' "$tok"
}

port_get() {   # port_get <path> <out-file> <token>
  local path="$1" out="$2" tok="$3" code
  code="$(curl -sS -o "$out" -w '%{http_code}' "https://api.port.io/v1/$path" -H "Authorization: Bearer $tok")" || {
    echo "❌ GET /v1/$path failed at the transport layer" >&2; return 1; }
  [ "$code" = "200" ] || { echo "❌ GET /v1/$path returned HTTP $code" >&2; return 1; }
}

main() {
  local list_only=0
  [ "${1-}" = "--list" ] && list_only=1

  command -v python3 >/dev/null 2>&1 || { echo "❌ python3 not found on PATH" >&2; exit 1; }

  # NOT `local`: the EXIT trap fires after main() returns, so a local would be out of scope and the
  # cleanup would die on `set -u` -- masking whatever real failure triggered the exit in the first
  # place. Found the first time this guard failed for a legitimate reason.
  work="$(mktemp -d)"; trap 'rm -rf "${work:-}"' EXIT

  # Every set comparison below is `comm`, which requires BOTH inputs sorted in the SAME collation.
  # Python's sort is byte-order; the shell's default locale is not, so `githubUser` and `github_user`
  # order differently and comm reports "input is not in sorted order" -- then, under a pipeline, that
  # warning is easy to miss while the comparison silently produces garbage. Pin the collation.
  export LC_ALL=C
  local bps sc ig
  bps="${PORT_LIVE_BLUEPRINTS_JSON:-}"; sc="${PORT_LIVE_SCORECARDS_JSON:-}"; ig="${PORT_LIVE_INTEGRATIONS_JSON:-}"
  if [ -z "$bps" ] || [ -z "$sc" ] || [ -z "$ig" ]; then
    command -v curl >/dev/null 2>&1 || { echo "❌ curl not found and no snapshot files given" >&2; exit 1; }
    local tok; tok="$(port_token)"
    bps="${bps:-$work/bps.json}";  [ -s "$bps" ] || port_get blueprints   "$bps" "$tok"
    sc="${sc:-$work/sc.json}";     [ -s "$sc" ]  || port_get scorecards   "$sc"  "$tok"
    ig="${ig:-$work/ig.json}";     [ -s "$ig" ]  || port_get integration  "$ig"  "$tok"
  fi
  for f in "$bps" "$sc" "$ig"; do
    [ -s "$f" ] || { echo "❌ live payload missing or empty: $f" >&2; exit 1; }
  done

  # Live sets.
  live_identifiers blueprint   "$bps" > "$work/live.bp"
  live_identifiers scorecard   "$sc"  > "$work/live.sc"
  live_identifiers integration "$ig"  > "$work/live.ig"
  integration_owned_blueprints "$ig"  > "$work/owned.bp"

  # Code sets.
  tf_identifiers port_blueprint   "$PORT_TF_DIR" > "$work/code.bp"
  tf_identifiers port_scorecard   "$PORT_TF_DIR" > "$work/code.sc"
  tf_identifiers port_integration "$PORT_TF_DIR" > "$work/code.ig"

  # Excused: Port system (`_`-prefixed) + integration-owned + the dormant accept-list.
  { grep '^_' "$work/live.bp" || true; cat "$work/owned.bp"
    printf '%s\n' "${DORMANT_UI_MANAGED[@]}" | cut -d'|' -f1
  } | sort -u > "$work/excused.bp"

  local fail=0

  printf '%-14s %6s %6s %8s %8s\n' "KIND" "LIVE" "CODE" "EXCUSED" "MISSING"
  local missing_bp missing_sc missing_ig
  missing_bp="$(comm -23 <(comm -23 "$work/live.bp" "$work/code.bp") "$work/excused.bp")"
  missing_sc="$(comm -23 "$work/live.sc" "$work/code.sc")"
  missing_ig="$(comm -23 "$work/live.ig" "$work/code.ig")"
  printf '%-14s %6s %6s %8s %8s\n' blueprints  "$(grep -c '' <"$work/live.bp")" "$(grep -c '' <"$work/code.bp")" \
    "$(grep -c '' <"$work/excused.bp")" "$(printf '%s' "$missing_bp" | grep -c '[^[:space:]]' || true)"
  printf '%-14s %6s %6s %8s %8s\n' scorecards  "$(grep -c '' <"$work/live.sc")" "$(grep -c '' <"$work/code.sc")" \
    0 "$(printf '%s' "$missing_sc" | grep -c '[^[:space:]]' || true)"
  printf '%-14s %6s %6s %8s %8s\n' integrations "$(grep -c '' <"$work/live.ig")" "$(grep -c '' <"$work/code.ig")" \
    0 "$(printf '%s' "$missing_ig" | grep -c '[^[:space:]]' || true)"

  if [ "$list_only" -eq 1 ]; then
    echo; echo "Deliberately UI-managed (the documented decision):"
    echo "  Port system blueprints (_-prefixed):"
    sed 's/^/    /' <(grep '^_' "$work/live.bp" || true)
    echo "  Integration-owned (derived from the live mappings, upgraded by the integration itself):"
    sed 's/^/    /' "$work/owned.bp"
    echo "  Dormant -- created on install, not mapped:"
    printf '%s\n' "${DORMANT_UI_MANAGED[@]}" | sed 's/|/  -- /; s/^/    /'
    echo; echo "Rebuild-order dependencies (codified blueprint -> uncodified target):"
    dangling_relation_targets "$bps" "$work/code.bp" | sed 's/^/    /'
    return 0
  fi

  if [ -n "$missing_bp" ]; then
    echo >&2
    echo "❌ live blueprints with NO definition in $PORT_TF_DIR:" >&2
    printf '%s\n' "$missing_bp" | sed 's/^/     /' >&2
    echo "   Either codify it, or add it to DORMANT_UI_MANAGED in this script WITH THE REASON." >&2
    fail=1
  fi
  if [ -n "$missing_sc" ]; then
    echo >&2; echo "❌ live scorecards with NO definition in $PORT_TF_DIR:" >&2
    printf '%s\n' "$missing_sc" | sed 's/^/     /' >&2; fail=1
  fi
  if [ -n "$missing_ig" ]; then
    echo >&2; echo "❌ live integrations with NO definition in $PORT_TF_DIR:" >&2
    printf '%s\n' "$missing_ig" | sed 's/^/     /' >&2; fail=1
  fi

  # A codified blueprint whose relation target is NOT codified is not an error -- it is the
  # documented rebuild order (install the integrations, THEN `tofu apply`). Print it every run so
  # the order stays a stated fact instead of a thing someone rediscovers during a restore.
  local dangling; dangling="$(dangling_relation_targets "$bps" "$work/code.bp")" || {
    echo "❌ could not evaluate relation targets" >&2; exit 1; }
  if [ -n "$dangling" ]; then
    echo
    echo "ℹ  rebuild order: these codified relations target integration-owned blueprints, so the"
    echo "   integrations must be installed BEFORE a from-scratch \`tofu apply\`:"
    printf '%s\n' "$dangling" | sed 's/^/     /'
  fi

  if [ "$fail" -ne 0 ]; then
    echo >&2
    echo "❌ Port's live schema is not fully described by the code. That is the B137 disease:" >&2
    echo "   a clean \`tofu plan\` cannot see a resource tofu was never told about." >&2
    exit 1
  fi
  echo
  echo "OK -- every live blueprint, scorecard and integration is either codified or documented as UI-managed."
}

if [ -z "${PORT_IAC_LIB:-}" ]; then
  main "$@"
fi
