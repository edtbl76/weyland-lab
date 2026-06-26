"""Publish real Postgres tables to Iceberg (Nessie warehouse) as table data products.

First Iceberg data products: the model catalog and the eval scores. Each reads its Postgres
table and overwrites it into Iceberg (idempotent). Depends on the upstream asset for ordering
so it runs after the table has been refreshed. See weyland_pipeline/iceberg_publish.py.
"""
from dagster import Output, asset

from weyland_pipeline.iceberg_publish import publish_table


@asset(
    group_name="catalog",
    deps=["model_catalog"],
    description="Publish the model_catalog Postgres table to Iceberg (Nessie warehouse) as a table data product.",
)
def iceberg_model_catalog(context) -> Output[dict]:
    rows = publish_table("catalog", "model_catalog", "SELECT * FROM model_catalog")
    context.log.info(f"Published Iceberg catalog.model_catalog: {rows} rows")
    return Output({"rows": rows}, metadata={"rows": rows, "iceberg_table": "catalog.model_catalog"})


@asset(
    group_name="eval",
    deps=["eval_scores"],
    description="Publish the eval_scores Postgres table to Iceberg (Nessie warehouse) as a table data product.",
)
def iceberg_eval_scores(context) -> Output[dict]:
    rows = publish_table("eval", "eval_scores", "SELECT * FROM eval_scores")
    context.log.info(f"Published Iceberg eval.eval_scores: {rows} rows")
    return Output({"rows": rows}, metadata={"rows": rows, "iceberg_table": "eval.eval_scores"})
