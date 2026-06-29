"""Open Food Facts — full product database (gzipped CSV, ~1.2GB compressed / ~9GB extracted)."""
from dagster import MetadataValue, Output, asset
from .health_common import health_minio, health_put, health_download


@asset(group_name="datasets_health", description="Land Open Food Facts gzipped CSV → health/raw/open_food_facts/.")
def open_food_facts_land(context) -> Output[dict]:
    client = health_minio()
    url = "https://static.openfoodfacts.org/data/en.openfoodfacts.org.products.csv.gz"
    context.log.info("Open Food Facts: streaming download (~1.2GB compressed)")
    try:
        data = health_download(url, timeout=3600)
        health_put(client, "open_food_facts/products.csv.gz", data, "application/gzip")
        context.log.info(f"open_food_facts/products.csv.gz → {len(data):,} bytes")
        return Output({"bytes": len(data)}, metadata={"bytes": MetadataValue.int(len(data))})
    except Exception as e:
        context.log.error(f"Open Food Facts: {e}")
        return Output({"error": str(e)}, metadata={"bytes": MetadataValue.int(0)})
