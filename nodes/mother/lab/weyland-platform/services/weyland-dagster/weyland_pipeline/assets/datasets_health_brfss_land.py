"""BRFSS — Behavioral Risk Factor Surveillance System (CDC). Annual CSV exports."""
from dagster import MetadataValue, Output, asset
from .health_common import health_minio, health_put, health_download, check_source_freshness

DATASETS = {
    "brfss_prevalence_2011_present": "https://data.cdc.gov/api/views/dttw-5yxu/rows.csv?accessType=DOWNLOAD",
    "brfss_smart_metro_2011_present": "https://data.cdc.gov/api/views/j32a-sa6u/rows.csv?accessType=DOWNLOAD",
}


@asset(group_name="datasets_health", description="Land BRFSS annual CSVs → health/raw/brfss/.")
def datasets_health_brfss_land(context) -> Output[dict]:
    first_url = next(iter(DATASETS.values()))
    if check_source_freshness(context, first_url):
        return Output({"skipped": True}, metadata={"skipped": MetadataValue.bool(True)})
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
