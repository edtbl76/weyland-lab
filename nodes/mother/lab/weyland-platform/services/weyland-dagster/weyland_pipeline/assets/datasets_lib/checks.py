"""Asset checks — the pre-hydration quality GATE. build_asset_checks(cfg) generates Dagster @asset_check
defs from the same DomainConfig that drives the transform, so every domain gets the gate for free (the
third factory: build_transform_assets → build_asset_checks → build_store_load_assets). Checks read the
transform's recorded materialization metadata (detail = per-table status; schemas = per-table column
names) — no data re-read.

v1: no_failures (block, per format) · expected_tables_present (block, parquet) · valid_column_names
(warn, parquet). The heavier Great Expectations → DataHub Assertions governance is the B77 tail."""
import re

from dagster import AssetCheckResult, AssetCheckSeverity, AssetKey, MetadataValue, asset_check

_VALID = re.compile(r"^[A-Za-z0-9_]+$")
_FORMATS = ("parquet", "arrow", "avro", "lance", "iceberg")


def _latest_meta(context, key: AssetKey) -> dict:
    """The asset's latest-materialization metadata as plain python (MetadataValue → .value)."""
    ev = context.instance.get_latest_materialization_event(key)
    if ev is None or ev.asset_materialization is None:
        return {}
    return {k: getattr(v, "value", v) for k, v in ev.asset_materialization.metadata.items()}


def build_asset_checks(cfg):
    d = cfg.domain
    checks = []

    # no_failures — per format: the transform recorded no ERROR and no 0-row "ok" table. The core gate.
    for fmt in _FORMATS:
        akey = AssetKey(f"datasets_{d}_{fmt}")

        @asset_check(asset=akey, name="no_failures", blocking=True,
                     description=f"No per-table ERROR or empty (0-row) output in datasets_{d}_{fmt}.")
        def _no_failures(context, _akey=akey):
            detail = _latest_meta(context, _akey).get("detail") or {}
            errors = {k: v for k, v in detail.items() if isinstance(v, str) and v.startswith("ERROR")}
            empty = {k: v for k, v in detail.items() if isinstance(v, str) and v.startswith("ok (0r ")}
            return AssetCheckResult(
                passed=not errors and not empty,
                severity=AssetCheckSeverity.ERROR,
                metadata={
                    "errors": MetadataValue.int(len(errors)),
                    "empty_tables": MetadataValue.int(len(empty)),
                    "failing": MetadataValue.json({**errors, **empty}),
                },
            )

        checks.append(_no_failures)

    parquet_key = AssetKey(f"datasets_{d}_parquet")
    expected = sorted(cfg.parquet_allow)

    @asset_check(asset=parquet_key, name="expected_tables_present", blocking=True,
                 description="Every allowlisted dataset produced at least one parquet table (catches a silently-missing source).")
    def _expected(context, _key=parquet_key, _exp=expected):
        detail = _latest_meta(context, _key).get("detail") or {}
        present = {k.split("/")[0] for k in detail}
        missing = sorted(set(_exp) - present)
        return AssetCheckResult(
            passed=not missing,
            severity=AssetCheckSeverity.ERROR,
            metadata={"missing": MetadataValue.json(missing), "datasets_present": MetadataValue.int(len(present))},
        )

    checks.append(_expected)

    @asset_check(asset=parquet_key, name="valid_column_names", blocking=False,
                 description="All silver column names are valid identifiers [A-Za-z0-9_] — a tripwire; sanitize_columns should already have normalized them.")
    def _names(context, _key=parquet_key):
        schemas = _latest_meta(context, _key).get("schemas") or {}
        bad = {k: [c for c in cols if not _VALID.match(c)] for k, cols in schemas.items()}
        bad = {k: v for k, v in bad.items() if v}
        return AssetCheckResult(
            passed=not bad,
            severity=AssetCheckSeverity.WARN,
            metadata={"tables_with_bad_names": MetadataValue.int(len(bad)), "detail": MetadataValue.json(bad)},
        )

    checks.append(_names)
    return checks
