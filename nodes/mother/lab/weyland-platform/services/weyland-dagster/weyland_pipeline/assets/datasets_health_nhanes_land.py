"""NHANES — National Health and Nutrition Examination Survey (CDC).
Key components from the 2017-2020 and 2015-2016 cycles as XPT (SAS transport) files.
"""
from dagster import MetadataValue, Output, asset
from .health_common import health_minio, health_put, health_download, check_source_freshness

# CDC reorganized wwwn.cdc.gov: the old /Nchs/Nhanes/<cycle>/<FILE>.XPT URLs now 302 to an HTML homepage
# (so the land step was silently saving HTML — verified 2026-06-30). Current pattern is
# /Nchs/Data/Nhanes/Public/<firstYear>/DataFiles/<FILE>.xpt (lowercase ext). 2017-18 = "2017", 2015-16 = "2015".
NHANES_FILES = [
    ("2017-2020/DEMO_J.XPT",   "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DEMO_J.xpt"),
    ("2017-2020/BMX_J.XPT",    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BMX_J.xpt"),
    ("2017-2020/BPX_J.XPT",    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BPX_J.xpt"),
    ("2017-2020/TCHOL_J.XPT",  "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/TCHOL_J.xpt"),
    ("2017-2020/DIQ_J.XPT",    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DIQ_J.xpt"),
    ("2017-2020/PAQ_J.XPT",    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/PAQ_J.xpt"),
    ("2017-2020/DR1TOT_J.XPT", "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DR1TOT_J.xpt"),
    ("2017-2020/DPQ_J.XPT",    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DPQ_J.xpt"),
    ("2017-2020/WHQ_J.XPT",    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/WHQ_J.xpt"),
    ("2017-2020/SLQ_J.XPT",    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/SLQ_J.xpt"),
    ("2015-2016/DEMO_I.XPT",   "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/DEMO_I.xpt"),
    ("2015-2016/BMX_I.XPT",    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/BMX_I.xpt"),
    ("2015-2016/PAQ_I.XPT",    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/PAQ_I.xpt"),
]


@asset(group_name="datasets_health", description="Land NHANES XPT files (2015-2020 cycles) → health/raw/nhanes/.")
def datasets_health_nhanes_land(context) -> Output[dict]:
    if check_source_freshness(context, NHANES_FILES[0][1]):
        return Output({"skipped": True}, metadata={"skipped": MetadataValue.bool(True)})
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
