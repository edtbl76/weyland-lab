"""datasets_lib — shared platform capabilities for the dataset domains (music, health, …).

Tonight's session proved the two domain transforms were ~90% copy-paste: every fix (streamed avro,
read-gating, per-file iceberg, size guard, null-coerce) had to be written twice. This package extracts
the shared mechanism so each domain is a thin DomainConfig + build_transform_assets(cfg) call, and each
land asset pulls io/freshness from here instead of a near-duplicate _common module.

Layout:
  io        — lakeFS/MinIO client, put/fput, raw-key prefixing (parameterized by repo/branch)
  freshness — last-materialization + remote-HEAD freshness checks, RefreshConfig.force override
  readers   — extension-dispatch reader (csv/gz/xpt/json), sanitize_columns, coerce_null_cols
  writers   — the 5 format writers (parquet/arrow/avro/lance/iceberg) + SkipTable / size cap / ice_ident
  config    — DomainConfig dataclass (repo, namespace, group, allowlists, deps)
  broker    — build_transform_assets(cfg) asset factory → the 5 format assets + commit
"""
