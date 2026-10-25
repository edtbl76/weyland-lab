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

# B233 (2026-10-23): Trino directly, as the `dbt` login over HTTPS (was the trino-noauth proxy, which only worked because
# Trino trusted X-Trino-User). `${TRINO_PASSWORD}` stays a placeholder in the stored datasource config and GE substitutes
# it from the environment at run time, so the file context on the ge-data PVC never holds the password. The lab CA comes
# from TRINO_CA (the dialect verifies against it).
CONN = os.environ.get("GE_TRINO_CONN", "trino://dbt:${TRINO_PASSWORD}@trino.data-mesh.svc.cluster.local:8443/iceberg")
CONNECT_ARGS = {"http_scheme": "https", "verify": os.environ.get("TRINO_CA", "/etc/weyland-ca/rootCA.pem")}
DOCS_ROOT = os.environ.get("GE_DOCS_ROOT", "/ge-data")     # GE context root; Data Docs land under <root>/uncommitted/data_docs
RESULTS = os.environ.get("GE_RESULTS", "/tmp/ge_results.json")

# (schema, table) in the `iceberg` catalog → DataHub name = iceberg.<schema>.<table>. Table assets (NOT query
# assets) so GE introspects the schema and the profiler can enumerate every column. Two marts + one big silver.
TARGETS = [
    ("dbt", "mart_country_health"),
    ("dbt", "mart_spotify_audio"),
    ("datasets_music", "spotify_tracks"),
]


def suite_validator(ctx, batch_request, suite_name):
    """A validator on a FRESH, empty suite named `suite_name`, on every run.

    The context is a FILE context on the ge-data PVC, so the suite from the last run is still there. The old call,
    get_validator(create_expectation_suite_with_name=...), refuses an existing suite: every run after the first died on
    its first table (B227 follow-on, 2026-10-25). add_or_update resets it to empty, so the profiler re-profiles the
    table as it is now instead of piling new expectations onto old ones."""
    ctx.add_or_update_expectation_suite(expectation_suite_name=suite_name)
    return ctx.get_validator(batch_request=batch_request, expectation_suite_name=suite_name)


def main():
    ctx = gx.get_context(mode="file", project_root_dir=DOCS_ROOT)
    # add_or_update, not add-then-get: the context is a FILE on the ge-data PVC, so a datasource created once kept its
    # first connection string forever (an old URL would have survived every code change).
    ds = ctx.sources.add_or_update_sql("trino", connection_string=CONN, kwargs={"connect_args": CONNECT_ARGS})

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
        validator = suite_validator(ctx, br, suite_name)
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
