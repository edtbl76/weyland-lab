#!/usr/bin/env bash
# DataHub catalog-coverage reconciliation (B158 follow-up A).
#
# WHY THIS EXISTS: the estate governs its INFRASTRUCTURE by CI — every metric-emitting workload is
# scraped (check-servicemonitor-coverage), visualized (check-dashboard-coverage), alerted
# (check-alert-coverage), and every Argo app is in the registry (check-app-registry). NONE of that
# reaches the DATA estate. Nothing fails when a mesh dataset that exists in Trino was never emitted to
# DataHub; data-governance completeness rests entirely on the emit job running plus eyes-on UAT at
# datahub.weyland.lab. That is the same no-positive-signal disease the ServiceMonitor guard was built
# to kill (a control that reports success while measuring nothing), left standing on the data plane —
# the B158 audit even caught the data-mesh-map product tile drifting from the emit code's real
# _PRODUCTS, by hand, because nothing checked it.
#
# It reconciles TWO planes; a table in the first but not the second is drift:
#
#   REALITY    the mesh tables Trino exposes   (iceberg.datasets_*.* silver/gold + iceberg.dbt.mart_*)
#   CATALOGED  the dataset URNs DataHub holds  (the emit's own graph.get_urns_by_filter([dataset]))
#
# FAIL CLOSED. The hard rule, the same one the ServiceMonitor guard is built around: an ABSENT result
# must never read as success. If the CATALOGED set comes back empty while REALITY is non-empty, that is
# overwhelmingly "GMS unreachable / DATAHUB_GMS_TOKEN missing," NOT "the whole mesh is uncatalogued" —
# so it exits 2 (could-not-run), never 1 (drift) and never 0 (clean). Likewise an empty REALITY set
# means Trino could not be read, not "there is nothing to catalog."
#
#   usage: scripts/check-datahub-coverage.sh [--list]
#          --list   print every mesh table and its verdict, exit 0
#
# EXIT CODES are distinct on purpose. 1 = the estate has a defect (uncatalogued mesh datasets).
# 2 = the guard could not do its job (Trino/GMS unreachable, no token, empty either side). Conflating
# them means a broken guard reads exactly like a clean estate.
#
# INPUTS. By default it reads the REALITY set from Trino (the noauth gateway) and the CATALOGED set
# from DataHub GMS. For testing, set either to a newline-separated fixture to skip the live fetch,
# exactly as check-servicemonitor-coverage.sh skips kubectl/Prometheus with SM_SNAPSHOT_JSON/TARGETS_JSON:
#
#   TRINO_TABLES   newline list of  schema.table   (mesh REALITY)     — skips Trino
#   DATAHUB_URNS   newline list of  dataset URNs or bare names        — skips GMS
#
# Sourced by scripts/tests/datahub-coverage.bats with DATAHUB_COVERAGE_LIB=1 to exercise is_cataloged
# without running main.
set -euo pipefail

TRINO_HTTP="${TRINO_HTTP:-http://trino-noauth.data-mesh.svc.cluster.local:8080}"
TRINO_USER="${TRINO_USER:-datahub-coverage}"
GMS_URL="${DATAHUB_GMS_URL:-http://datahub-datahub-gms.data-mesh.svc.cluster.local:8080}"
GMS_TOKEN="${DATAHUB_GMS_TOKEN:-}"

# --- accepted, with the reason -------------------------------------------------------------------
#
# One row per mesh table that legitimately exists in Trino without a DataHub entity:
#   <schema.table>|<why it is fine, in terms a reader can re-check>
# Same posture as check-servicemonitor-coverage.sh / check-pip-audit-ignores.sh: an exception states
# the CONDITION that makes it fine, so it is re-checkable rather than trusted. Empty today.
ACCEPTED=()

is_accepted() { # is_accepted <schema.table>
  local row e_entry
  for row in "${ACCEPTED[@]:-}"; do
    [ -z "$row" ] && continue
    IFS="|" read -r e_entry _ <<<"$row"
    [ "$e_entry" = "$1" ] && return 0
  done
  return 1
}

# --- the decision --------------------------------------------------------------------------------
#
# is_cataloged <schema.table> <newline-separated DataHub names> -> exit 0 catalogued / 1 not.
#
# Match rule: some DataHub name's LAST TWO dotted segments, rejoined, equal "schema.table". This
# absorbs platform prefixes (iceberg.dbt.mart_x, trino.datasets_finance.price_daily) and the sibling
# twins the emit merges, without a fragile full-string compare — and it does NOT match on table name
# alone, so a finance URN can never satisfy a music table of the same name.
is_cataloged() { # is_cataloged <schema.table> <newline names> -> 0 catalogued / 1 not
  # ONE awk pass reduces every name to its final two dotted segments (not a fork per name — the
  # catalogued set is the whole DataHub estate, ~5k datasets, and a fork-per-name inner loop timed out
  # at 2 minutes on the first live run). The awk result is captured to a variable FIRST, then grep tests
  # membership over that herestring. It must NOT be `awk ... | grep -Fxq`: with `set -o pipefail`,
  # grep -q short-circuits on the first match and closes the pipe, awk (still emitting thousands of
  # lines) dies with SIGPIPE, and pipefail returns awk's 141 — so a real MATCH reads as no-match. That
  # bug is invisible to small fixtures (awk finishes before grep exits) and fired on every live run.
  local key="$1" names="$2" reduced
  reduced="$(awk -F. '{ if (NF >= 2) print $(NF-1) "." $NF; else print $0 }' <<<"$names")"
  grep -Fxq -- "$key" <<<"$reduced"
}

# --- live fetch (skipped whenever the fixture env var is SET, even if empty) ----------------------

fetch_trino_tables() { # -> newline schema.table for the mesh data estate, or non-zero on failure
  # datasets_* silver/gold + the dbt marts (the products). Trino REST: POST a statement, follow nextUri.
  local sql body next rows out=""
  sql="SELECT table_schema || '.' || table_name FROM iceberg.information_schema.tables
       WHERE table_schema LIKE 'datasets\_%' ESCAPE '\\'
          OR (table_schema = 'dbt' AND table_name LIKE 'mart\_%' ESCAPE '\\')"
  body="$(curl -sS -f -X POST "$TRINO_HTTP/v1/statement" \
            -H "X-Trino-User: $TRINO_USER" -H 'Content-Type: text/plain' \
            --data "$sql")" || return 1
  while :; do
    rows="$(jq -r '.data // [] | .[][]' <<<"$body" 2>/dev/null)" || return 1
    [ -n "$rows" ] && out+="$rows"$'\n'
    next="$(jq -r '.nextUri // empty' <<<"$body")"
    [ -z "$next" ] && break
    # Trino returns nextUri as an ABSOLUTE url on its own advertised host (e.g. trino.data-mesh.svc),
    # which is not reachable through a proxy/port-forward. Re-point scheme+authority at the endpoint we
    # were actually given (trino-noauth); the query path + id are preserved, so it follows the same query.
    next="$TRINO_HTTP$(sed -E 's#^[a-zA-Z]+://[^/]+##' <<<"$next")"
    body="$(curl -sS -f "$next" -H "X-Trino-User: $TRINO_USER")" || return 1
    # a FAILED state must be loud, not an empty (=clean-looking) result
    [ "$(jq -r '.stats.state // ""' <<<"$body")" = "FAILED" ] && return 1
  done
  printf '%s' "$out" | sed '/^$/d'
}

fetch_datahub_names() { # -> newline dataset names from GMS, or non-zero on failure
  [ -z "$GMS_TOKEN" ] && return 1   # no token => cannot read => fail closed (2), never "nothing catalogued"
  local scroll="" q resp urns out="" total="" got=0 page
  # scrollId is passed as a GraphQL VARIABLE (null on the first page) — no jq expression ever leaks into
  # the query text, which is what returned HTTP 400 in the first cut.
  local gql='query($s:String){ scrollAcrossEntities(input:{types:[DATASET],query:"*",count:1000,scrollId:$s}){ nextScrollId total searchResults{ entity{ urn } } } }'
  while :; do
    q="$(jq -nc --arg gql "$gql" --arg s "$scroll" '{query:$gql, variables:{s: ($s | select(. != "") // null)}}')"
    resp="$(curl -sS -f -X POST "$GMS_URL/api/graphql" \
              -H "Authorization: Bearer $GMS_TOKEN" -H 'Content-Type: application/json' \
              --data "$q")" || return 1
    [ -z "$total" ] && total="$(jq -r '.data.scrollAcrossEntities.total // empty' <<<"$resp")"
    urns="$(jq -r '.data.scrollAcrossEntities.searchResults[]?.entity.urn // empty' <<<"$resp")" || return 1
    [ -z "$urns" ] && break   # exhausted (empty page) — also guards against a non-null scrollId that yields nothing
    page="$(grep -c . <<<"$urns")"; got=$((got + page))
    out+="$urns"$'\n'
    scroll="$(jq -r '.data.scrollAcrossEntities.nextScrollId // empty' <<<"$resp")"
    [ -z "$scroll" ] && break
  done
  # COMPLETENESS: the scroll (search_after, no point-in-time) can under-return under load. If we did not
  # collect every dataset GMS says exists, we CANNOT grade coverage — refuse rather than cry wolf over
  # datasets that were simply never fetched. Fail closed (main turns this into exit 2).
  if [ -n "$total" ] && [ "$got" -lt "$total" ]; then
    echo "GMS scroll incomplete: fetched $got of $total datasets — refusing partial coverage" >&2
    return 1
  fi
  # urn:li:dataset:(urn:li:dataPlatform:<plat>,<name>,<env>) -> <name>
  printf '%s' "$out" | sed -E 's/^urn:li:dataset:\(urn:li:dataPlatform:[^,]+,(.+),[^,]+\)$/\1/' | sed '/^$/d'
}

main() {
  local list=0 arg
  for arg in "$@"; do
    case "$arg" in
      --list) list=1 ;;
      *) echo "unknown arg: $arg" >&2; return 2 ;;
    esac
  done

  local reality catalogued
  if [ -n "${TRINO_TABLES+x}" ]; then reality="$TRINO_TABLES"; else reality="$(fetch_trino_tables)" || { echo "could not read mesh tables from Trino ($TRINO_HTTP)" >&2; return 2; }; fi
  if [ -n "${DATAHUB_URNS+x}" ]; then catalogued="$DATAHUB_URNS"; else catalogued="$(fetch_datahub_names)" || { echo "could not read datasets from DataHub GMS ($GMS_URL) — token set? " >&2; return 2; }; fi

  reality="$(printf '%s\n' "$reality" | sed '/^$/d')"
  catalogued="$(printf '%s\n' "$catalogued" | sed '/^$/d')"

  # FAIL CLOSED: an empty either side is a failed read, not an answer.
  if [ -z "$reality" ]; then echo "REALITY set is empty — Trino read failed; refusing to grade coverage (exit 2)" >&2; return 2; fi
  if [ -z "$catalogued" ]; then echo "CATALOGED set is empty while Trino has tables — GMS unreachable or token missing; refusing to report 'all uncatalogued' (exit 2)" >&2; return 2; fi

  local key uncat=() verdict tbl
  while IFS= read -r tbl; do
    [ -z "$tbl" ] && continue
    key="$tbl"
    if is_cataloged "$key" "$catalogued"; then
      verdict="cataloged"
    elif is_accepted "$key"; then
      verdict="accepted"
    else
      verdict="UNCATALOGED"
      uncat+=("$key")
    fi
    [ "$list" -eq 1 ] && printf '  %-40s %s\n' "$key" "$verdict"
  done <<<"$reality"

  if [ "$list" -eq 1 ]; then return 0; fi

  if [ "${#uncat[@]}" -gt 0 ]; then
    echo "DRIFT — ${#uncat[@]} mesh table(s) exist in Trino but are NOT in DataHub:" >&2
    printf '  - %s\n' "${uncat[@]}" >&2
    echo "Fix: run the datahub_catalog_emit_job (or add the dataset to its domain rules), then re-check." >&2
    return 1
  fi

  local n_real; n_real="$(printf '%s\n' "$reality" | grep -c . || true)"
  echo "OK — all $n_real mesh table(s) in Trino are catalogued in DataHub."
  return 0
}

if [ -z "${DATAHUB_COVERAGE_LIB:-}" ]; then
  main "$@"
fi
