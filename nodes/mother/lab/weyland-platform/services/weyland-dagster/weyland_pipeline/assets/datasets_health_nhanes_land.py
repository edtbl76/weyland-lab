"""NHANES — National Health and Nutrition Examination Survey (CDC).
Key components from the 2017-2020 and 2015-2016 cycles as XPT (SAS transport) files.
"""
from dagster import MetadataValue, Output, asset
from .health_common import health_minio, health_put, health_download

NHANES_FILES = [
    ("2017-2020/DEMO_J.XPT",   "https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/DEMO_J.XPT"),
    ("2017-2020/BMX_J.XPT",    "https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/BMX_J.XPT"),
    ("2017-2020/BPX_J.XPT",    "https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/BPX_J.XPT"),
    ("2017-2020/TCHOL_J.XPT",  "https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/TCHOL_J.XPT"),
    ("2017-2020/DIQ_J.XPT",    "https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/DIQ_J.XPT"),
    ("2017-2020/PAQ_J.XPT",    "https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/PAQ_J.XPT"),
    ("2017-2020/DR1TOT_J.XPT", "https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/DR1TOT_J.XPT"),
    ("2017-2020/DPQ_J.XPT",    "https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/DPQ_J.XPT"),
    ("2017-2020/WHQ_J.XPT",    "https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/WHQ_J.XPT"),
    ("2017-2020/SLQ_J.XPT",    "https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/SLQ_J.XPT"),
    ("2015-2016/DEMO_I.XPT",   "https://wwwn.cdc.gov/Nchs/Nhanes/2015-2016/DEMO_I.XPT"),
    ("2015-2016/BMX_I.XPT",    "https://wwwn.cdc.gov/Nchs/Nhanes/2015-2016/BMX_I.XPT"),
    ("2015-2016/PAQ_I.XPT",    "https://wwwn.cdc.gov/Nchs/Nhanes/2015-2016/PAQ_I.XPT"),
]


@asset(group_name="datasets_health", description="Land NHANES XPT files (2015-2020 cycles) → health/raw/nhanes/.")
def datasets_health_nhanes_land(context) -> Output[dict]:
    client = health_minio()
    out = {}
    for local_name, url in NHANES_FILES:
        try:
            data = health_download(url, timeout=300)
            health_put(client, f"nhanes/{local_name}", data)
            out[local_name] = len(data)
            context.log.info(f"nhanes/{local_name} → {len(data):,} bytes")
        except Exception as e:
            out[local_name] = f"ERROR: {e}"
            context.log.warning(f"NHANES {local_name}: {e}")
    ok = sum(1 for v in out.values() if isinstance(v, int))
    return Output(out, metadata={"files": MetadataValue.int(ok), "detail": MetadataValue.json(out)})
