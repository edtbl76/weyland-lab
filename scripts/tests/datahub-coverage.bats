#!/usr/bin/env bats
# B158 (follow-up A) — DataHub catalog-coverage reconciliation.
#
# WHY THIS EXISTS: the estate has a coherent "govern by CI" story for INFRASTRUCTURE — every
# metric-emitting workload is scraped (check-servicemonitor-coverage), visualized (dashboard) and
# alerted (alert-coverage), and every Argo app is in the registry (check-app-registry). None of it
# reaches the DATA estate. Nothing fails when a mesh dataset that exists in Trino was never emitted
# to DataHub — data-governance completeness rests entirely on the emit job running plus eyes-on UAT.
# That is the same no-positive-signal disease the ServiceMonitor guard was built to kill, left
# standing on the data plane (the B158 audit even caught the data-mesh-map product tile drifting from
# the emit code's real _PRODUCTS, by hand, because nothing checks it).
#
# It reconciles TWO planes and any disagreement is a defect:
#
#   REALITY    the mesh tables Trino exposes   (iceberg.datasets_*.* silver/gold + iceberg.dbt.mart_*)
#   CATALOGED  the dataset URNs DataHub holds  (graph.get_urns_by_filter(entity_types=[dataset]))
#
# A table in REALITY but absent from CATALOGED is drift. The hard part is the SAME as the ServiceMonitor
# guard: an ABSENT result must never read as success. If the CATALOGED set comes back empty while
# REALITY is non-empty, that is overwhelmingly "GMS is unreachable / the token is missing," NOT "the
# whole mesh is uncatalogued" — so it FAILS CLOSED as exit 2 (could-not-run), never exit 1 (drift) and
# never exit 0 (clean). Exit 1 = the estate has a real gap; exit 2 = the guard could not do its job.

setup() {
  load helper
  setup_stubs
  GUARD="$REPO_ROOT/scripts/check-datahub-coverage.sh"
}

teardown() {
  teardown_stubs
}

lib_source() {
  DATAHUB_COVERAGE_LIB=1 source "$GUARD"
}

@test "the guard exists and is executable" {
  [ -f "$GUARD" ]
  [ -x "$GUARD" ]
}

# --- is_cataloged: the whole decision ------------------------------------------------------------
#
# is_cataloged <schema.table> <newline-separated DataHub names> -> exit 0 cataloged / 1 not.
# The match rule: some DataHub name's LAST TWO dotted segments equal [schema, table]. This absorbs
# platform prefixes (iceberg.dbt.mart_x, trino.datasets_finance.price_daily) and the sibling twins the
# emit merges, without a fragile full-string compare.

@test "is_cataloged: a silver table catalogued under its bare schema.table matches" {
  lib_source
  run is_cataloged "datasets_finance.price_daily" "datasets_finance.price_daily
datasets_music.spotify_tracks"
  [ "$status" -eq 0 ]
}

@test "is_cataloged: a mart catalogued with an iceberg.dbt. platform prefix matches on the last two segments" {
  lib_source
  run is_cataloged "dbt.mart_price_daily" "iceberg.dbt.mart_price_daily
iceberg.datasets_finance.fred_macro"
  [ "$status" -eq 0 ]
}

@test "is_cataloged: a table present in Trino but absent from DataHub is NOT catalogued" {
  lib_source
  run is_cataloged "datasets_finance.price_daily" "datasets_music.spotify_tracks
iceberg.dbt.mart_macro_indicators"
  [ "$status" -eq 1 ]
}

@test "is_cataloged: a sibling twin (same table under two platforms) still matches once" {
  lib_source
  run is_cataloged "datasets_finance.company_meta" "iceberg.datasets_finance.company_meta
trino.datasets_finance.company_meta"
  [ "$status" -eq 0 ]
}

@test "is_cataloged: a table whose NAME matches but under the wrong schema does NOT match" {
  lib_source
  # price_daily exists in finance; a music.price_daily must not be considered catalogued by a finance URN
  run is_cataloged "datasets_music.price_daily" "iceberg.datasets_finance.price_daily"
  [ "$status" -eq 1 ]
}

# --- main: reconciliation + fail-closed ----------------------------------------------------------
#
# Live fetch is skipped when TRINO_TABLES and DATAHUB_URNS are set (fixture-gated), exactly as the
# ServiceMonitor guard skips kubectl/Prometheus with SM_SNAPSHOT_JSON/TARGETS_JSON.

@test "main: every Trino table catalogued -> exit 0" {
  TRINO_TABLES="datasets_finance.price_daily
dbt.mart_price_daily" \
  DATAHUB_URNS="iceberg.datasets_finance.price_daily
iceberg.dbt.mart_price_daily" \
  run "$GUARD"
  [ "$status" -eq 0 ]
}

@test "main: an uncatalogued Trino table -> exit 1 and names it" {
  TRINO_TABLES="datasets_finance.price_daily
datasets_finance.filings_text" \
  DATAHUB_URNS="iceberg.datasets_finance.price_daily" \
  run "$GUARD"
  [ "$status" -eq 1 ]
  [[ "$output" == *"datasets_finance.filings_text"* ]]
}

@test "main: empty DataHub set with a non-empty Trino set FAILS CLOSED as exit 2, not drift" {
  TRINO_TABLES="datasets_finance.price_daily" \
  DATAHUB_URNS="" \
  run "$GUARD"
  [ "$status" -eq 2 ]
}

@test "main: empty Trino set (cannot determine what should exist) is exit 2, not a clean pass" {
  TRINO_TABLES="" \
  DATAHUB_URNS="iceberg.datasets_finance.price_daily" \
  run "$GUARD"
  [ "$status" -eq 2 ]
}

@test "main: --list prints every table with a verdict and exits 0 even on drift" {
  TRINO_TABLES="datasets_finance.price_daily
datasets_finance.filings_text" \
  DATAHUB_URNS="iceberg.datasets_finance.price_daily" \
  run "$GUARD" --list
  [ "$status" -eq 0 ]
  [[ "$output" == *"price_daily"* ]]
  [[ "$output" == *"filings_text"* ]]
}

# --- anti-drift ----------------------------------------------------------------------------------
#
# The CronJob (k8s/monitoring/datahub-coverage.yaml) runs an EMBEDDED copy of this guard from a
# ConfigMap. Two copies drift silently on both sides — the cluster runs logic nothing tests while the
# suite stays green. The repo script is the source; scripts/embed-datahub-coverage.sh regenerates the
# copy, and this asserts they match.
@test "the CronJob's embedded script is byte-identical to the tested guard" {
  local manifest="$REPO_ROOT/nodes/mother/lab/weyland-platform/k8s/monitoring/datahub-coverage.yaml"
  [ -f "$manifest" ]
  extract_configmap_script "$manifest" "check-datahub-coverage.sh" > "$BATS_TEST_TMPDIR/embedded.sh"
  diff "$GUARD" "$BATS_TEST_TMPDIR/embedded.sh"
}
