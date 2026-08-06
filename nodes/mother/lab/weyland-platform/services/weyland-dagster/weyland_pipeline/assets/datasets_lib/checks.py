"""Asset checks — the pre-hydration quality GATE. build_asset_checks(cfg) generates Dagster @asset_check
defs from the same DomainConfig that drives the transform, so every domain gets the gate for free (the
third factory: build_transform_assets → build_asset_checks → build_store_load_assets). Checks read the
transform's recorded materialization metadata (detail = per-table status; schemas = per-table column
names) — no data re-read.

v1: no_failures (block, per format) · expected_tables_present (block, parquet) · valid_column_names
(warn, parquet). The heavier Great Expectations → DataHub Assertions governance is the B77 tail.

NOTE: @asset_check reads the function signature and treats EVERY parameter as an asset input, so the only
parameter may be `context` — per-check values (asset key, allowlist) are captured via closures (factory
functions), never default args.
"""
import re

from dagster import AssetCheckResult, AssetCheckSeverity, AssetKey, MetadataValue, asset_check

_VALID = re.compile(r"^[A-Za-z0-9_]+$")
_FORMATS = ("parquet", "arrow", "avro", "lance", "iceberg")

# Known-benign all-null columns per source folder (the `table` part of the "table/name" key) — structurally or
# optionally empty at the source, NOT parse failures. From the B77 triage 2026-08-06 (all 17 verified benign; the
# USDA FK confirmed via Trino — inputs are referenced by sr_code/sr_description, not fdc_id_of_input_food). Keeping
# these out of the WARN means a NEW all-null column stands out as a real regression instead of hiding in the noise.
ALL_NULL_ALLOWLIST = {
    "who_gho": {"Comments", "DataSourceDim", "DataSourceDimType", "Dim1", "Dim1Type",
                "Dim2", "Dim2Type", "Dim3", "Dim3Type", "High", "Low"},   # GHO OData fixed schema — unused dim/annotation slots
    "nhanes": {"BMIHEAD"},                                                # head circumference — infant-only measure
    "nhis": {"CHFLG_A", "OGFLG_A", "OPFLG_A", "PRPLCOV2_C_A"},            # edit/imputation + conditional coverage flags
    "usda_fooddata": {"footnote", "max_value", "fdc_id_of_input_food"},   # optional text/measure + SR-referenced input FK
}


def _latest_meta(context, key: AssetKey) -> dict:
    """The asset's latest-materialization metadata as plain python (MetadataValue → .value)."""
    ev = context.instance.get_latest_materialization_event(key)
    if ev is None or ev.asset_materialization is None:
        return {}
    return {k: getattr(v, "value", v) for k, v in ev.asset_materialization.metadata.items()}


def build_asset_checks(cfg):
    d = cfg.domain
    checks = []

    def _make_no_failures(fmt):
        akey = AssetKey(f"datasets_{d}_{fmt}")

        @asset_check(asset=akey, name="no_failures", blocking=True,
                     description=f"No per-table ERROR / empty (0-row) output in datasets_{d}_{fmt}.")
        def _chk(context):
            detail = _latest_meta(context, akey).get("detail") or {}
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

        return _chk

    for fmt in _FORMATS:
        checks.append(_make_no_failures(fmt))

    parquet_key = AssetKey(f"datasets_{d}_parquet")
    expected = sorted(cfg.parquet_allow)

    @asset_check(asset=parquet_key, name="expected_tables_present", blocking=True,
                 description="Every allowlisted dataset produced at least one parquet table (catches a silently-missing source).")
    def _expected(context):
        detail = _latest_meta(context, parquet_key).get("detail") or {}
        present = {k.split("/")[0] for k in detail}
        missing = sorted(set(expected) - present)
        return AssetCheckResult(
            passed=not missing,
            severity=AssetCheckSeverity.ERROR,
            metadata={"missing": MetadataValue.json(missing), "datasets_present": MetadataValue.int(len(present))},
        )

    checks.append(_expected)

    @asset_check(asset=parquet_key, name="valid_column_names", blocking=False,
                 description="All silver column names are valid identifiers [A-Za-z0-9_] — a tripwire; sanitize_columns should already have normalized them.")
    def _names(context):
        schemas = _latest_meta(context, parquet_key).get("schemas") or {}
        bad = {k: [c for c in cols if not _VALID.match(c)] for k, cols in schemas.items()}
        bad = {k: v for k, v in bad.items() if v}
        return AssetCheckResult(
            passed=not bad,
            severity=AssetCheckSeverity.WARN,
            metadata={"tables_with_bad_names": MetadataValue.int(len(bad)), "detail": MetadataValue.json(bad)},
        )

    checks.append(_names)

    @asset_check(asset=parquet_key, name="no_all_null_columns", blocking=False,
                 description="No silver column is 100% null — a silent parse/source failure (the class that produced the fma URL-column + spotify empty column). WARN, not block.")
    def _all_null(context):
        meta = _latest_meta(context, parquet_key)
        detail = meta.get("detail") or {}
        nulls = meta.get("nulls") or {}
        bad = {}
        for key, cols in nulls.items():
            m = re.match(r"ok \((\d+)r", str(detail.get(key, "")))
            if not m:
                continue
            rc = int(m.group(1))
            allow = ALL_NULL_ALLOWLIST.get(key.split("/")[0], ())
            all_null = [c for c, nc in cols.items() if rc and nc >= rc and c not in allow]
            if all_null:
                bad[key] = all_null
        return AssetCheckResult(
            passed=not bad,
            severity=AssetCheckSeverity.WARN,
            metadata={"tables_with_all_null_columns": MetadataValue.int(len(bad)), "detail": MetadataValue.json(bad)},
        )

    checks.append(_all_null)
    return checks
