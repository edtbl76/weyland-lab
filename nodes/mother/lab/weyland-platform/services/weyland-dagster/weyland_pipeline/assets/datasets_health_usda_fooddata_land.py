"""USDA FoodData Central — bulk CSV download (~400MB zip, ~2GB extracted)."""
from dagster import MetadataValue, Output, asset
from .health_common import health_minio, health_download_zip


@asset(group_name="datasets_health", description="Land USDA FoodData Central CSVs → health/raw/usda_fooddata/.")
def datasets_health_usda_fooddata_land(context) -> Output[dict]:
    client = health_minio()
    url = "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_csv_2024-10-31.zip"
    context.log.info("USDA FoodData: downloading bulk zip (~400MB)")
    try:
        count = health_download_zip(client, url, "usda_fooddata", context.log, timeout=1800)
        return Output({"files": count}, metadata={"files": MetadataValue.int(count)})
    except Exception as e:
        context.log.error(f"USDA FoodData: {e}")
        return Output({"error": str(e)}, metadata={"files": MetadataValue.int(0)})
