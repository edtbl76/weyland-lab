# B80 — DataHub Completeness Hardening (running list) — HONEST STATUS 2026-07-11

Reality check (cluster-wide recon, all 3255 datasets): the catalog is dominated by OPERATIONAL data —
postgres 2076 (GlitchTip/Kuma/Keycloak/Lightdash/etc. app DBs), grafana 367. Data-mesh datasets are the
minority (~trino 127 + iceberg 120 + dbt 23 + the Tier-2 store copies + vectors/graph). "Done" = the SURFACE
is actually populated across the intended scope — NOT that code was written.

Coverage now:  domain 3255/3255 · owner 3255/3255 · ≥1 term 917/3255 · stats/contracts/assertions 16/3255.

## SCOPE DECISION NEEDED (blocks honest completion)
Does the FULL treatment (terms/desc/stats/contracts/assertions) apply to the 2443 operational app-DB + grafana
datasets, or is the target the ~few-hundred DATA-MESH datasets (marts/gold/Tier-2 store copies/vectors/graph)?
Operational tables (span_id/trace_id/issue_id/monitor_id) are infra internals — data-mesh governance is a poor fit.

## Status per finding
- [x] #2 Domain coverage — DONE 3255/3255 (0 domainless). CAVEAT: 2443 are Platform&Ops fallback (mostly correct: infra=ops).
- [x] #9 Owners — DONE 3255/3255 (CorpGroup `weyland` = Technical Owner). Verify group entity renders.
- [ ] #1 Tag audit — PARTIAL. Materialized 5 tag entities (gold/silver/bronze/mart/feast) but did NOT audit coverage or apply tags across the catalog. Not done.
- [ ] #3/#6 Field desc/terms/tags — PARTIAL. 917/3255 have >=1 term (data-mesh datasets). Descriptions barely touched. Operational majority unmapped. NOT done.
- [ ] #7 Stats — NOT done. 16/3255 (Soda marts+gold only). Breadth needs ingestion-source PROFILING (postgres/mysql/mongo/clickhouse recipes) + emit for custom stores.
- [ ] #5 Data Contracts — NOT done. 16/3255. Curated-per-table; real target = data products (needs a scope call).
- [ ] #4 Queries — NOT done. 7/3255 (marts only).
- [ ] #8 Assertions — NOT done. 16/3255 (marts + WHO/BRFSS gold). Schema-aware emit now EXISTS (enabler), coverage does not.

## What genuinely landed (mechanism proven, scope narrow)
- Soda emitters schema-aware; gold health scan works (17/17).
- mesh_vocabulary +15 terms → 1496 new field-attaches across 339 datasets.
- emit_tags/emit_ownership/emit_queries/emit_domains-fallback wired into datahub_catalog_emit_job.
