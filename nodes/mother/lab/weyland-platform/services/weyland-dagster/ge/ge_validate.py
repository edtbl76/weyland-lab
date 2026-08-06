"""Great Expectations 0.18 validation runner — B77 part (b). Run by the isolated /opt/ge-venv (shelled out from
ge_validate_op, the same pattern as soda_scan_op). For each showcase table: a Fluent Trino SQL *table* asset (so GE
introspects the real schema) → UserConfigurableProfiler builds a per-column suite (types, non-null, ranges, value
sets, uniqueness) → a checkpoint validates it → Data Docs are built. Writes a combined validation-results JSON that
the MAIN Dagster env's emit_ge_assertions() turns into DataHub Assertions (acryl-datahub 1.7 dropped the native GE
action, so we hand-roll the emit).

GE runs isolated because its sqlalchemy/marshmallow pins clash with the dagster+dbt+datahub main env — so this file
imports ONLY great_expectations/stdlib, never weyland_pipeline. The GE→DataHub bridge is the JSON at GE_RESULTS.
"""
import json
import os

import great_expectations as gx
from great_expectations.profile.user_configurable_profiler import UserConfigurableProfiler

# trino-noauth proxy (the path Soda already uses) — auth-stripped; user `dbt` is Ranger-authorized on these schemas.
CONN = os.environ.get("GE_TRINO_CONN", "trino://dbt@trino-noauth.data-mesh.svc.cluster.local:8080/iceberg")
DOCS_ROOT = os.environ.get("GE_DOCS_ROOT", "/ge-data")     # GE context root; Data Docs land under <root>/uncommitted/data_docs
RESULTS = os.environ.get("GE_RESULTS", "/tmp/ge_results.json")

# (schema, table) in the `iceberg` catalog → DataHub name = iceberg.<schema>.<table>. Table assets (NOT query
# assets) so GE introspects the schema and the profiler can enumerate every column. Two marts + one big silver.
TARGETS = [
    ("dbt", "mart_country_health"),
    ("dbt", "mart_spotify_audio"),
    ("datasets_music", "spotify_tracks"),
]


def main():
    ctx = gx.get_context(mode="file", project_root_dir=DOCS_ROOT)
    try:
        ds = ctx.sources.add_sql("trino", connection_string=CONN)
    except Exception:
        ds = ctx.get_datasource("trino")

    out = []
    for schema, table in TARGETS:
        fq = f"iceberg.{schema}.{table}"
        aname = fq.replace(".", "_")
        try:
            asset = ds.add_table_asset(name=aname, table_name=table, schema_name=schema)
        except Exception:
            asset = ds.get_asset(aname)
        br = asset.build_batch_request()
        suite_name = f"ge_{aname}"

        # AUTO-PROFILE every column → a rich suite (GE's differentiator).
        validator = ctx.get_validator(batch_request=br, create_expectation_suite_with_name=suite_name)
        UserConfigurableProfiler(profile_dataset=validator).build_suite()
        validator.save_expectation_suite(discard_failed_expectations=False)

        cp = ctx.add_or_update_checkpoint(
            name=f"cp_{suite_name}",
            validations=[{"batch_request": br, "expectation_suite_name": suite_name}],
        )
        cpr = cp.run()
        for _, vr in cpr.run_results.items():
            v = vr["validation_result"]
            out.append({
                "dataset": fq,
                "statistics": v.statistics,
                "results": [r.to_json_dict() for r in v.results],
            })
        suite = ctx.get_expectation_suite(suite_name)
        print(f"{fq}: {len(suite.expectations)} expectations profiled, checkpoint success={cpr.success}")

    ctx.build_data_docs()
    with open(RESULTS, "w") as f:
        json.dump(out, f)
    print(f"wrote {RESULTS} ({len(out)} datasets); Data Docs under {DOCS_ROOT}/uncommitted/data_docs/")


if __name__ == "__main__":
    main()
