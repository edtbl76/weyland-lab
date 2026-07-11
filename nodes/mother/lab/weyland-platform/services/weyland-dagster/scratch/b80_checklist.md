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

## Phase 3 — coverage sweep  [AFTER verifying 1+2 — genuinely iterative, schema-aware]
- [ ] #3 / #6 **Field desc/terms/tags** — extend `mesh_vocabulary` for gold-source + Tier-2 columns (big_five `e1..o10`, etc.). Needs an unmatched-field recon first.
- [ ] #8 **Assertions on more tables** — expand Soda beyond the 7 marts. BLOCKED on: the emit funcs hardcode `iceberg.dbt.{table}` URNs — gold tables are `iceberg.datasets_*.{table}`, so the emit must become schema/dataSource-aware first.

## Notes / decisions
- big_five is a GOLD SOURCE (`iceberg.datasets_health`), not a mart — assertions/contracts target the 7 marts, gold gaps are partly by-design.
- Everything git-emitted (no durable UI layer). Verify each surface after the rebuild.
