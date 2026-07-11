# B80 — DataHub Completeness Hardening (running list)

Priority-ordered. Each item DONE only when its DataHub surface actually populates (verified), not when code is written.

## Phase 1 — reuse Soda output (cheap, one emit path)  [CODE DONE — pending rebuild+verify]
- [~] #7 **Stats** — `emit_soda_profiles()` (DatasetProfile: rowCount + per-field null/min/max from -srf metrics), called from `soda_scan_op`.
- [~] #5 **Data Contracts** — `emit_data_contracts()` (DataContract per mart referencing the Soda assertion URNs).

## Phase 2 — git-emit extensions  [CODE DONE — pending rebuild+verify]
- [~] #2 **Domain coverage** — `emit_domains` fallback: business data → its domain, everything else → Platform & Ops. Zero domainless.
- [~] #9 **Owners** — `emit_ownership()` — CorpGroup `weyland` = TECHNICAL_OWNER of every dataset.
- [~] #4 **Queries** — `emit_queries()` — 7 canonical example `Query` entities (one per mart).
- [~] #1 **Tag audit** — `emit_tags()` — materialize gold/silver/bronze/mart/feast as first-class Tag entities (found: they were referenced but never entity-emitted).

## Phase 3 — coverage sweep  [CODE DONE — pending rebuild+verify]
- [~] #3 / #6 **Field desc/terms/tags** — added 15 `mesh_vocabulary` terms for the HIGH-FREQUENCY unmapped clusters (WHO GHO spatialdim/timedim/numericvalue/indicatorcode/parentlocation/datasourcedim; CDC BRFSS location/taxonomy/data_value/sample_size/geolocation; NHANES seqn; USDA fdc_id; year; track_id). Generic id/value/text left unmapped on purpose. NOTE: big_five raw OCEAN items (single-dataset long tail, uncertain col names) left — the mart's trait columns carry the OCEAN terms.
- [~] #8 **Assertions on more tables** — made the Soda emitters SCHEMA-AWARE (`_SODA_DS_SCHEMA` dataSource→schema map). Added `weyland_health` data source + `health_gold.yml` (WHO GHO + BRFSS gold, row_count + numericvalue emptiness tripwire). `soda_scan_op` now runs both scans (marts + gold) and emits each.

## Notes / decisions
- big_five is a GOLD SOURCE (`iceberg.datasets_health`), not a mart — assertions/contracts target the 7 marts, gold gaps are partly by-design.
- Everything git-emitted (no durable UI layer). Verify each surface after the rebuild.
