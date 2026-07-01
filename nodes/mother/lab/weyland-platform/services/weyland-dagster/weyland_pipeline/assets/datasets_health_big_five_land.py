"""Big Five personality traits — Open Psychometrics IPIP dataset (~19.7k responses, ~57 columns).

The archive's data.csv is TAB-separated despite the .csv name; convert it to real comma-CSV on land so the
transform's comma reader parses the ~57 columns instead of collapsing every row into one (which it did —
silver came out 19719r × 1c, and the MySQL load couldn't use it)."""
import io as _io
import zipfile

import pyarrow.csv as pacsv
from dagster import MetadataValue, Output, asset
from .health_common import health_minio, health_put, health_download, should_skip, RefreshConfig


@asset(group_name="datasets_health", description="Land Big Five IPIP personality data → health/raw/big_five/ (TSV→CSV).")
def datasets_health_big_five_land(context, config: RefreshConfig) -> Output[dict]:
    client = health_minio()
    url = "https://openpsychometrics.org/_rawdata/BIG5.zip"
    if should_skip(context, config, url=url):  # materialize with {"force": true} to bypass freshness
        return Output({"skipped": True}, metadata={"skipped": MetadataValue.bool(True)})
    context.log.info("Big Five: downloading zip")
    data = health_download(url)
    out = {}
    with zipfile.ZipFile(_io.BytesIO(data)) as z:
        for name in z.namelist():
            content = z.read(name)
            if name.endswith(".csv"):
                # data.csv is TAB-separated — re-emit as comma-CSV so the ~57 columns parse downstream.
                t = pacsv.read_csv(_io.BytesIO(content), parse_options=pacsv.ParseOptions(delimiter="\t"))
                buf = _io.BytesIO()
                pacsv.write_csv(t, buf)
                content, ct = buf.getvalue(), "text/csv"
                context.log.info(f"big_five/{name}: TSV → CSV, {t.num_columns} columns")
            else:
                ct = "text/plain"
            health_put(client, f"big_five/{name}", content, ct)
            out[name] = len(content)
            context.log.info(f"big_five/{name} → {len(content):,} bytes")
    return Output(out, metadata={"files": MetadataValue.int(len(out)), "detail": MetadataValue.json(out)})
