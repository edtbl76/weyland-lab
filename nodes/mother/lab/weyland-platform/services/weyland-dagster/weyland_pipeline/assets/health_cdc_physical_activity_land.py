"""CDC Physical Activity datasets from the CDC open data portal."""
from dagster import MetadataValue, Output, asset
from .health_common import health_minio, health_put, health_download

DATASETS = {
    "physical_activity_adults":             "https://data.cdc.gov/api/views/ivfh-b3de/rows.csv?accessType=DOWNLOAD",
    "physical_activity_youth":              "https://data.cdc.gov/api/views/fqe6-n26c/rows.csv?accessType=DOWNLOAD",
    "nutrition_physical_activity_obesity":  "https://data.cdc.gov/api/views/hn4x-zwk7/rows.csv?accessType=DOWNLOAD",
}


@asset(group_name="datasets_health", description="Land CDC Physical Activity CSVs → health/raw/cdc_physical_activity/.")
def cdc_physical_activity_land(context) -> Output[dict]:
    client = health_minio()
    out = {}
    for name, url in DATASETS.items():
        try:
            data = health_download(url)
            health_put(client, f"cdc_physical_activity/{name}.csv", data, "text/csv")
            out[name] = len(data)
            context.log.info(f"cdc_physical_activity/{name}.csv → {len(data):,} bytes")
        except Exception as e:
            out[name] = f"ERROR: {e}"
            context.log.warning(f"CDC Physical Activity {name}: {e}")
    ok = sum(1 for v in out.values() if isinstance(v, int))
    return Output(out, metadata={"files": MetadataValue.int(ok), "detail": MetadataValue.json(out)})
