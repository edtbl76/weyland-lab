"""BRFSS — Behavioral Risk Factor Surveillance System (CDC). Annual CSV exports."""
from dagster import MetadataValue, Output, asset
from .health_common import health_minio, health_put, health_download

DATASETS = {
    "brfss_2022": "https://data.cdc.gov/api/views/dttw-5yxu/rows.csv?accessType=DOWNLOAD",
    "brfss_2021": "https://data.cdc.gov/api/views/8953-7fz5/rows.csv?accessType=DOWNLOAD",
    "brfss_2020": "https://data.cdc.gov/api/views/j32a-sa6u/rows.csv?accessType=DOWNLOAD",
    "brfss_selected_metro": "https://data.cdc.gov/api/views/j32a-sa6u/rows.csv?accessType=DOWNLOAD",
}


@asset(group_name="datasets_health", description="Land BRFSS annual CSVs → health/raw/brfss/.")
def brfss_land(context) -> Output[dict]:
    client = health_minio()
    out = {}
    for name, url in DATASETS.items():
        try:
            data = health_download(url, timeout=900)
            health_put(client, f"brfss/{name}.csv", data, "text/csv")
            out[name] = len(data)
            context.log.info(f"brfss/{name}.csv → {len(data):,} bytes")
        except Exception as e:
            out[name] = f"ERROR: {e}"
            context.log.warning(f"BRFSS {name}: {e}")
    ok = sum(1 for v in out.values() if isinstance(v, int))
    return Output(out, metadata={"files": MetadataValue.int(ok), "detail": MetadataValue.json(out)})
