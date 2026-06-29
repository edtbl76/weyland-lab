"""NHIS — National Health Interview Survey (CDC). Annual zip/CSV files.
Public alternative to UK Biobank — ~100k US adults/year, health + lifestyle + demographics."""
from dagster import MetadataValue, Output, asset
from .health_common import health_minio, health_download_zip, check_source_freshness

DATASETS = {
    "nhis_adult_2022": "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/NHIS/2022/adult22csv.zip",
    "nhis_adult_2021": "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/NHIS/2021/adult21csv.zip",
    "nhis_adult_2020": "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/NHIS/2020/adult20csv.zip",
}


@asset(group_name="datasets_health", description="Land NHIS annual survey CSVs → health/raw/nhis/.")
def datasets_health_nhis_land(context) -> Output[dict]:
    first_url = next(iter(DATASETS.values()))
    if check_source_freshness(context, first_url):
        return Output({"skipped": True}, metadata={"skipped": MetadataValue.bool(True)})
    client = health_minio()
    out = {}
    for name, url in DATASETS.items():
        try:
            count = health_download_zip(client, url, f"nhis/{name}", context.log, timeout=600)
            out[name] = count
        except Exception as e:
            out[name] = f"ERROR: {e}"
            context.log.warning(f"NHIS {name}: {e}")
    ok = sum(v for v in out.values() if isinstance(v, int))
    return Output(out, metadata={"files": MetadataValue.int(ok), "detail": MetadataValue.json(out)})
