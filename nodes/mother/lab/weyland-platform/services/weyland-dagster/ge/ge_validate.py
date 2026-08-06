"""Great Expectations 0.18 validation runner — B77 part (b). Run by the isolated /opt/ge-venv (shelled out from
ge_validate_op, the same pattern as soda_scan_op). For each showcase table: a Fluent Trino SQL datasource → the
Onboarding Data Assistant AUTO-PROFILES an expectation suite from the data → a checkpoint validates it → Data Docs
are built. Writes a combined validation-results JSON that the MAIN Dagster env's emit_ge_assertions() turns into
DataHub Assertions (acryl-datahub 1.7 dropped the native GE action, so we hand-roll the emit).

GE runs isolated because its sqlalchemy/marshmallow pins clash with the dagster+dbt+datahub main env — so this file
imports ONLY great_expectations/stdlib, never weyland_pipeline. The GE→DataHub bridge is the JSON at GE_RESULTS.
"""
import json
import os

import great_expectations as gx

# trino-noauth proxy (the path Soda already uses) — auth-stripped, so the user is cosmetic.
CONN = os.environ.get("GE_TRINO_CONN", "trino://dbt@trino-noauth.data-mesh.svc.cluster.local:8080/iceberg")  # user `dbt` = the passwordless path Soda uses; Ranger authorizes dbt on iceberg.{dbt,datasets_*}
DOCS_ROOT = os.environ.get("GE_DOCS_ROOT", "/ge-data")     # GE context root; Data Docs land under <root>/uncommitted/data_docs
RESULTS = os.environ.get("GE_RESULTS", "/tmp/ge_results.json")
SAMPLE = int(os.environ.get("GE_SAMPLE", "20000"))          # cap profiling cost on big silver tables

# Showcase set — (DataHub dataset name = fully-qualified trino name). Two marts (small, curated) + one big silver.
TARGETS = [
    "iceberg.dbt.mart_country_health",
    "iceberg.dbt.mart_spotify_audio",
    "iceberg.datasets_music.spotify_tracks",
]


def main():
    ctx = gx.get_context(mode="file", project_root_dir=DOCS_ROOT)
    try:
        ds = ctx.sources.add_sql("trino", connection_string=CONN)
    except Exception:
        ds = ctx.get_datasource("trino")

    out = []
    for table in TARGETS:
        aname = table.replace(".", "_")
        try:
            asset = ds.add_query_asset(name=aname, query=f"SELECT * FROM {table} LIMIT {SAMPLE}")
        except Exception:
            asset = ds.get_asset(aname)
        br = asset.build_batch_request()
        suite_name = f"ge_{aname}"

        # AUTO-PROFILE: the Onboarding Data Assistant generates the suite FROM the data (GE's differentiator).
        assistant_result = ctx.assistants.onboarding.run(batch_request=br)
        suite = assistant_result.get_expectation_suite(expectation_suite_name=suite_name)
        ctx.add_or_update_expectation_suite(expectation_suite=suite)

        cp = ctx.add_or_update_checkpoint(
            name=f"cp_{suite_name}",
            validations=[{"batch_request": br, "expectation_suite_name": suite_name}],
        )
        cpr = cp.run()
        for _, vr in cpr.run_results.items():
            v = vr["validation_result"]
            out.append({
                "dataset": table,
                "statistics": v.statistics,
                "results": [r.to_json_dict() for r in v.results],
            })
        print(f"{table}: {len(suite.expectations)} expectations profiled, checkpoint success={cpr.success}")

    ctx.build_data_docs()
    with open(RESULTS, "w") as f:
        json.dump(out, f)
    print(f"wrote {RESULTS} ({len(out)} datasets); Data Docs under {DOCS_ROOT}/uncommitted/data_docs/")


if __name__ == "__main__":
    main()
