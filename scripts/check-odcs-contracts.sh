#!/usr/bin/env bash
# ODCS data-contract conformance guard (B157 / B158 follow-up E).
#
# WHY THIS EXISTS: the mesh had contract SUBSTANCE scattered across dbt tests, Soda checks, DataHub
# DataContracts and the DomainConfig, but no single declarative contract and nothing that FAILED when a
# contract was malformed or missing a required piece. B157 adopts the Open Data Contract Standard (ODCS,
# Bitol / Linux Foundation) as the canonical shape (a justified lab SUBSET — see the decision doc
# docs/concepts/data-contracts-odcs.md). This is the conformance gate: every `*.odcs.yaml` under the
# contracts root must carry the adopted required fields and be internally well-formed, or CI fails.
#
# It is a STRUCTURAL gate (does the contract declare what the standard requires), runnable in CI with no
# cluster. Asserting each declared column actually exists in Trino is a natural next pass (needs the
# cluster) — tracked as a follow-on, not built here; the declared columns were verified against Trino by
# hand when the finance contracts were authored (2026-09-05).
#
#   usage: scripts/check-odcs-contracts.sh [--list]
#          --list   print every contract file and its verdict, exit 0
#
# EXIT CODES: 0 = every contract conforms. 1 = a contract is malformed/incomplete. 2 = the guard could
# not run (no python/PyYAML, or the contracts root is missing) — never conflated with a clean pass.
#
# INPUTS: CONTRACTS_ROOT (default the platform contracts dir) — override to a fixture tree for tests.
# Sourced by scripts/tests/odcs-contracts.bats with ODCS_CONTRACTS_LIB=1 to exercise validate_doc.
set -euo pipefail

_here="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
CONTRACTS_ROOT="${CONTRACTS_ROOT:-$_here/nodes/mother/lab/weyland-platform/services/weyland-dagster/contracts}"
TRINO_HTTP="${TRINO_HTTP:-http://trino-noauth.data-mesh.svc.cluster.local:8080}"
TRINO_USER="${TRINO_USER:-odcs-conformance}"

# --- optional live schema conformance (--check-schema) -------------------------------------------
# Assert every column a contract DECLARES actually exists in its Trino physical table. Needs the
# cluster; not the default. Same Trino REST + nextUri-rewrite as check-datahub-coverage.sh.
trino_query() { # trino_query <sql> -> first-column rows, or non-zero (fail closed)
  local sql="$1" body next rows out=""
  body="$(curl -sS -f -X POST "$TRINO_HTTP/v1/statement" \
            -H "X-Trino-User: $TRINO_USER" -H 'Content-Type: text/plain' --data "$sql")" || return 1
  while :; do
    rows="$(jq -r '.data // [] | .[][]' <<<"$body" 2>/dev/null)" || return 1
    [ -n "$rows" ] && out+="$rows"$'\n'
    next="$(jq -r '.nextUri // empty' <<<"$body")"; [ -z "$next" ] && break
    next="$TRINO_HTTP$(sed -E 's#^[a-zA-Z]+://[^/]+##' <<<"$next")"
    body="$(curl -sS -f "$next" -H "X-Trino-User: $TRINO_USER")" || return 1
    [ "$(jq -r '.stats.state // ""' <<<"$body")" = "FAILED" ] && return 1
  done
  printf '%s' "$out" | sed '/^$/d'
}

# contract_tables <json> -> one line per schema table: "<physicalName>\t<col,col,...>"
contract_tables() {
  jq -r '.schema[]? | [ (.physicalName // .name), ((.properties // []) | map(.name) | join(",")) ] | @tsv' <<<"$1"
}

# schema_errors <json> -> prints "table.col not in Trino" for each declared column that is absent; 0 iff none.
# Returns 2 (not 1) on a Trino read failure so the caller fails closed rather than reading "no drift".
schema_errors() {
  local json="$1" phys cols actual missing=0 col
  while IFS=$'\t' read -r phys cols; do
    [ -z "$phys" ] && continue
    # iceberg.datasets_finance.price_daily -> catalog / schema / table
    local cat sch tbl
    cat="${phys%%.*}"; local rest="${phys#*.}"; sch="${rest%%.*}"; tbl="${rest#*.}"
    actual="$(trino_query "SELECT column_name FROM ${cat}.information_schema.columns WHERE table_schema='${sch}' AND table_name='${tbl}'")" \
      || { echo "TRINO_UNREACHABLE $phys" >&2; return 2; }
    [ -z "$actual" ] && { echo "  ! $phys — no columns found in Trino (wrong physicalName?)"; missing=1; continue; }
    IFS=',' read -ra want <<<"$cols"
    for col in "${want[@]}"; do
      [ -z "$col" ] && continue
      grep -Fxq -- "$col" <<<"$actual" || { echo "  ! $phys.$col — declared but not in Trino"; missing=1; }
    done
  done < <(contract_tables "$json")
  [ "$missing" -eq 0 ]
}

# yaml_to_json <file> -> the doc as JSON on stdout, or non-zero (fail closed) if it will not parse.
yaml_to_json() {
  python3 - "$1" <<'PY' || return 1
import json, sys
try:
    import yaml
except Exception:
    print("FATAL: PyYAML not available", file=sys.stderr); raise SystemExit(2)
try:
    with open(sys.argv[1], encoding="utf-8") as fh:
        doc = yaml.safe_load(fh)
except Exception as e:
    print(f"unparseable YAML: {e}", file=sys.stderr); raise SystemExit(1)
if not isinstance(doc, dict):
    print("top level is not a mapping", file=sys.stderr); raise SystemExit(1)
print(json.dumps(doc))
PY
}

# validate_doc <json> -> prints one error per line for every rule broken; exit 0 iff no errors.
# The adopted ODCS subset (see the decision doc): the fundamentals that make a contract usable + governable.
validate_doc() {
  jq -r '
    . as $d |
    # scalar fundamentals — each yields a message string or nothing
    ([
      (if (($d.apiVersion // "") | test("^v3")) then empty else "apiVersion must be v3.x" end),
      (if $d.kind == "DataContract" then empty else "kind must be DataContract" end),
      (if (($d.id // "") != "") then empty else "missing id" end),
      (if (($d.name // "") != "") then empty else "missing name" end),
      (if (($d.version // "") | test("^[0-9]+\\.[0-9]+\\.[0-9]+$")) then empty else "version must be semver x.y.z" end),
      (if (($d.status // "") != "") then empty else "missing status" end),
      (if (($d.domain // "") != "") then empty else "missing domain" end),
      (if (($d.dataProduct // "") != "") then empty else "missing dataProduct" end),
      (if (($d.description | type) == "object" and (($d.description.purpose // "") != "")) then empty else "description.purpose is required" end),
      (if (($d.servers | type) == "array" and ($d.servers | length) > 0) then empty else "at least one server is required" end),
      (if (($d.schema | type) == "array" and ($d.schema | length) > 0) then empty else "schema must be a non-empty array" end),
      (if (($d.team | type) == "array" and (($d.team // []) | map(.role) | index("owner")) != null) then empty else "a team member with role owner is required" end)
    ]
    # a schema table with no properties
    + [ ($d.schema // [])[] | select(type == "object") | select((.properties | type) != "array" or (.properties | length) == 0) | "schema table \(.name // "?") has no properties" ]
    # a property missing name or logicalType
    + [ ($d.schema // [])[] | select(type == "object") | (.properties // [])[] | select(type == "object") | select((.name // "") == "" or (.logicalType // "") == "") | "a property is missing name or logicalType" ]
    ) | .[]
  ' <<<"$1"
}

main() {
  local list=0 checkschema=0 arg
  for arg in "$@"; do case "$arg" in
    --list) list=1 ;;
    --check-schema) checkschema=1 ;;
    *) echo "unknown arg: $arg" >&2; return 2 ;;
  esac; done
  command -v python3 >/dev/null 2>&1 || { echo "python3 not found" >&2; return 2; }
  command -v jq      >/dev/null 2>&1 || { echo "jq not found" >&2; return 2; }
  [ -d "$CONTRACTS_ROOT" ] || { echo "contracts root missing: $CONTRACTS_ROOT (exit 2)" >&2; return 2; }

  local files n=0 bad=0 f json errs ids=""
  files="$(find "$CONTRACTS_ROOT" -type f -name '*.odcs.yaml' | sort)"
  while IFS= read -r f; do
    [ -z "$f" ] && continue
    n=$((n + 1))
    if ! json="$(yaml_to_json "$f")"; then
      echo "  ❌ $(basename "$f") — could not parse" >&2; bad=$((bad + 1)); continue
    fi
    errs="$(validate_doc "$json")"
    # id uniqueness across the set
    local id; id="$(jq -r '.id // ""' <<<"$json")"
    if [ -n "$id" ] && printf '%s\n' "$ids" | grep -Fxq -- "$id"; then
      errs="$(printf '%s\nduplicate id: %s' "$errs" "$id")"
    fi
    [ -n "$id" ] && ids="$ids"$'\n'"$id"
    # live column conformance (opt-in) — appends any declared-but-absent columns to this file's errors
    if [ "$checkschema" -eq 1 ]; then
      local serr rc
      serr="$(schema_errors "$json")"; rc=$?
      if [ "$rc" -eq 2 ]; then echo "❌ Trino unreachable — cannot check schema conformance (exit 2)" >&2; return 2; fi
      [ -n "$serr" ] && errs="$(printf '%s\n%s' "$errs" "$serr")"
    fi
    if [ -n "$errs" ]; then
      bad=$((bad + 1))
      echo "  ❌ $(basename "$f"):" >&2
      printf '%s\n' "$errs" | sed 's/^/       - /' >&2
    elif [ "$list" -eq 1 ]; then
      printf '  ✓ %s\n' "$(basename "$f")"
    fi
  done <<<"$files"

  if [ "$list" -eq 1 ]; then echo "listed $n contract(s)."; return 0; fi
  if [ "$bad" -ne 0 ]; then echo "❌ $bad of $n ODCS contract(s) do not conform." >&2; return 1; fi
  echo "OK — $n ODCS contract(s) conform to the adopted subset."
  return 0
}

if [ -z "${ODCS_CONTRACTS_LIB:-}" ]; then
  main "$@"
fi
