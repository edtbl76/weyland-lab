"""Big Five personality traits — Open Psychometrics IPIP-NEO dataset (N≈1M responses)."""
import io, zipfile
from dagster import MetadataValue, Output, asset
from .health_common import health_minio, health_put, health_download


@asset(group_name="datasets_health", description="Land Big Five IPIP personality data → health/raw/big_five/.")
def big_five_land(context) -> Output[dict]:
    client = health_minio()
    url = "https://openpsychometrics.org/_rawdata/BIG5.zip"
    context.log.info("Big Five: downloading zip")
    data = health_download(url)
    out = {}
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            content = z.read(name)
            ct = "text/csv" if name.endswith(".csv") else "text/plain"
            health_put(client, f"big_five/{name}", content, ct)
            out[name] = len(content)
            context.log.info(f"big_five/{name} → {len(content):,} bytes")
    return Output(out, metadata={"files": MetadataValue.int(len(out)), "detail": MetadataValue.json(out)})
