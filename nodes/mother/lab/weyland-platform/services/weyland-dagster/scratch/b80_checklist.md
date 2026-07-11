# B80 — DataHub Completeness Hardening (running list)

Priority-ordered. Each item DONE only when its DataHub surface actually populates (verified), not when code is written.

## Phase 1 — reuse Soda output (cheap, one emit path)
- [ ] #7 **Stats** — emit `DatasetProfile` (rowCount + per-field null/min/max) from the Soda `-srf` results → Stats tab lights up for the 7 marts. `emit_soda_profiles()` in datahub_emit.py, called from `soda_scan_op`.
- [ ] #5 **Data Contracts** — emit `DataContract` per mart referencing the already-emitted Soda assertion URNs (+ schema) → Data Contract tab. `emit_data_contracts()`.

## Phase 2 — git-emit extensions
- [ ] #2 **Domain coverage** — find domainless datasets, extend `emit_domains` URN patterns until every dataset resolves a domain.
- [ ] #9 **Owners** — emit `Ownership` (emangini / Weyland group as TECHNICAL_OWNER) across managed datasets.
- [ ] #4 **Queries** — git-emit canonical example `Query` entities per mart → Queries tab.

## Phase 3 — coverage sweep
- [ ] #1 **Tag audit** — enumerate emitted tags + coverage/consistency (informs #3).
- [ ] #3 / #6 **Field desc/terms/tags** — extend `mesh_vocabulary` patterns to cover gold-source + Tier-2 columns (big_five `e1..o10`, etc.).
- [ ] #8 **Assertions on more tables** — decide + expand Soda scope beyond the 7 marts (gold sources / Tier-2).

## Notes / decisions
- big_five is a GOLD SOURCE (`iceberg.datasets_health`), not a mart — assertions/contracts target the 7 marts, gold gaps are partly by-design.
- Everything git-emitted (no durable UI layer). Verify each surface after the rebuild.
