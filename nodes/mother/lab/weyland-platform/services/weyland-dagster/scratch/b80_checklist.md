# B80 — DataHub Completeness Hardening — HONEST FULL-SURFACE STATE (updated 2026-07-11)

Catalog: 3282 datasets, 51,703 fields. Measure surfaces at the RIGHT granularity (field-level, not "dataset has ≥1").

## DONE — cluster-wide by rule
- [x] **Domains** — 3282/3282 (0 domainless; business→domain, else Platform&Ops fallback). `emit_domains`.
- [x] **Owners** — 3282/3282 (CorpGroup `weyland` = Technical Owner). `emit_ownership`.
- [x] **Dataset tags** — 3282/3282 (layer + store-tier + source, read-merge). `emit_tags`+`emit_tag_assignments`.

## SUBSTANTIALLY DONE — field descriptions
- [x] **Field descriptions** — **69% of fields** (desc-or-tag) up from 37%. Via SOURCE-DOC ingest (`datasets_field_docs.py`
  + `emit_field_docs`) for 14 datasets from published field dictionaries: OFF 90%, USDA FDC 100%, FMA/audioset/
  musiccaps/gtzan/uci 98-100%, big_five 99%, lastfm 100%, brfss/cdc_physical 100%, musicbrainz 89%, **NHANES 469
  exact (100%)**, **NHIS 223 exact (General-module only)**. Plus class-level fallback (`_field_class`).
  - RESIDUAL: NHIS disease-question vars (angev_a… — only 42 matched; they're in the topic/frequency codebooks, not
    the nofreq General codebook). Operational-postgres app columns that don't classify. → the last ~31%.

## PARTIAL — the "lot to do"
- [x] **Field TAGS** — **98%** (50718/51703) via name-class (`_field_class`) + SCHEMA-TYPE fallback (`_type_class`):
      every typed field gets a class tag even when the name doesn't classify. Residual ~2% = untyped/null-type
      fields with no name match. DONE 2026-07-11.
- [x] **Field TERMS (glossary)** — **48%** (24865/51703) up from 26%. `emit_source_terms`: (a) 13 NEW audio-DSP/
      nutrition terms the name-vocab lacked (MFCC, chroma CENS/CQT/STFT, tonnetz, spectral-contrast, echonest
      timbre/social/highlevel/track-meta, timbre avg/cov, nutrient-per-100g); (b) EXTERNAL source citations
      (sourceRef+sourceUrl) on 32 existing terms (WHO/CDC/MusicBrainz/OTel/Sentry/USDA); (c) DESCRIPTION-based
      attach (11101 fields) — the name-attach missed them. Remaining 52% = generic class-fallback columns,
      DELIBERATELY skipped (a bare "measure" isn't worth a term). DONE 2026-07-11.
- [ ] **NHIS full** — the disease/condition question vars need the topic-module OR frequency codebook (Adult-codebook.pdf
      w/ frequencies) — a follow-up extraction.

## CURATED / BOUNDED (can't auto-populate 3282 — by nature)
- [x] **Stats** — **2417/3282 (73%) — ACCEPTED CEILING** (2026-07-11). Ingestion profiling (postgres 2076/2096,
      clickhouse, cassandra) + custom-emit (qdrant/weaviate/lancedb/opensearch/duckdb/mysql/timescaledb) +
      cockroach custom — all row-bearing recipe/custom stores are lit. The 865 missing: ~622 genuinely non-tabular
      (grafana 373, dagster 93, file-formats 103, neo4j 26, dbt 23, kafka 4) — won't fake a rowCount; ~185
      lakehouse iceberg/trino tables (Trino count(*) emit would reach ~78%) — DECLINED as not worth it; 27 stale
      ghosts (opensearch 19 / timescale 8) → soft-delete cleanup, tracked below.
- [~] **Data Contracts** — 16 (marts + gold, referencing Soda assertions). Expand Soda scope to widen.
- [~] **Assertions** — 16 (marts + gold via Soda). Expand Soda scope to widen.
- [ ] **Queries** — 7 (marts, example queries). Extend to more datasets (low value for operational).

## Also open
- [ ] Stale-entry cleanup (opensearch 19, timescale 8 = dropped store objects lingering) → soft-delete.
- [ ] GPM UI (gatekeeper.weyland.lab) live-check; enable soda_quality_schedule.

## Mechanisms (reusable)
- `datahub_emit.py`: emit_domains/ownership/tags/tag_assignments/mesh_glossary/field_docs/queries; soda emit
  (assertions/profiles/contracts, schema-aware); emit_cockroachdb_profiles; store profiles (`_emit_profile`).
- `datasets_field_docs.py`: per-dataset {col: desc} from source dictionaries (exact + prefix + suffix + GLOBAL_COLS).
- `scripts/extract_survey_labels.py`: NHANES XPT labels (pyreadstat) + NHIS codebook PDF (pdfplumber).
