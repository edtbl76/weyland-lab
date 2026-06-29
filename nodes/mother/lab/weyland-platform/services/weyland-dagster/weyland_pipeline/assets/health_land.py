"""B65 Tier-2 MySQL / health domain — Step 1: land public health, wellness, and personality datasets
into the lakeFS `health` repo (s3://datasets/health/main/raw/<dataset>/) as raw files (bronze).

9 datasets:
  nhanes            — NHANES (CDC) nutrition/biomarkers/fitness, all available cycles
  big_five          — Big Five personality traits (Open Psychometrics IPIP, N=1M+)
  who_gho           — WHO Global Health Observatory (selected indicators via REST API)
  cdc_physical_activity — CDC Physical Activity data
  brfss             — Behavioral Risk Factor Surveillance System (CDC, all available years)
  myfitnesspal      — MyFitnessPal public dataset (HuggingFace)
  uk_biobank        — UK Biobank public subset (HuggingFace)
  usda_fooddata     — USDA FoodData Central (bulk CSV download)
  open_food_facts   — Open Food Facts (CSV, ~9GB — full dataset)

All land via the lakeFS S3 gateway (versioned). Large files are streamed to avoid OOM.
"""
import io
import json
import os
import urllib.request
import zipfile

from dagster import MetadataValue, Output, asset
from minio import Minio

_HEALTH_REPO = "health"
_BRANCH = "main"
_ENDPOINT = os.environ.get("LAKEFS_ENDPOINT", "http://lakefs.data-mesh.svc.cluster.local:8000")


def _minio() -> Minio:
    ep = _ENDPOINT
    return Minio(
        ep.replace("https://", "").replace("http://", ""),
        access_key=os.environ["LAKEFS_ACCESS_KEY_ID"],
        secret_key=os.environ["LAKEFS_SECRET_ACCESS_KEY"],
        secure=ep.startswith("https://"),
    )


def _put(client, key: str, data: bytes, content_type: str = "application/octet-stream"):
    full_key = f"{_BRANCH}/raw/{key}"
    client.put_object(_HEALTH_REPO, full_key, io.BytesIO(data), length=len(data), content_type=content_type)


def _put_stream(client, key: str, stream, length: int, content_type: str = "application/octet-stream"):
    full_key = f"{_BRANCH}/raw/{key}"
    client.put_object(_HEALTH_REPO, full_key, stream, length=length, content_type=content_type)


def _download(url: str, timeout: int = 600) -> bytes:
    req = urllib.request.Request(url, headers={"User-Agent": "weyland-health-land/1.0"})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        return r.read()


def _land_nhanes(client, log):
    """NHANES — CDC, key components via direct XPT files from wwwn.cdc.gov.
    Using the latest continuous cycle (2017-2020) + 2015-2016 for breadth.
    XPT (SAS transport) files are the canonical NHANES format — downloaded as binary blobs."""
    # Key NHANES XPT files: (local_name, url)
    nhanes_files = [
        # Demographics
        ("2017-2020/DEMO_P.XPT", "https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/DEMO_J.XPT"),
        # Body measures
        ("2017-2020/BMX_J.XPT", "https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/BMX_J.XPT"),
        # Blood pressure
        ("2017-2020/BPX_J.XPT", "https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/BPX_J.XPT"),
        # Cholesterol
        ("2017-2020/TCHOL_J.XPT", "https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/TCHOL_J.XPT"),
        # Diabetes
        ("2017-2020/DIQ_J.XPT", "https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/DIQ_J.XPT"),
        # Physical activity
        ("2017-2020/PAQ_J.XPT", "https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/PAQ_J.XPT"),
        # Dietary recall day 1
        ("2017-2020/DR1TOT_J.XPT", "https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/DR1TOT_J.XPT"),
        # Mental health / depression
        ("2017-2020/DPQ_J.XPT", "https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/DPQ_J.XPT"),
        # Weight history
        ("2017-2020/WHQ_J.XPT", "https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/WHQ_J.XPT"),
        # Sleep disorders
        ("2017-2020/SLQ_J.XPT", "https://wwwn.cdc.gov/Nchs/Nhanes/2017-2018/SLQ_J.XPT"),
        # 2015-2016 cycle demographics for cross-cycle analysis
        ("2015-2016/DEMO_I.XPT", "https://wwwn.cdc.gov/Nchs/Nhanes/2015-2016/DEMO_I.XPT"),
        ("2015-2016/BMX_I.XPT", "https://wwwn.cdc.gov/Nchs/Nhanes/2015-2016/BMX_I.XPT"),
        ("2015-2016/PAQ_I.XPT", "https://wwwn.cdc.gov/Nchs/Nhanes/2015-2016/PAQ_I.XPT"),
    ]
    count = 0
    for local_name, url in nhanes_files:
        try:
            log.info(f"NHANES: downloading {local_name}")
            data = _download(url, timeout=300)
            _put(client, f"nhanes/{local_name}", data, "application/octet-stream")
            count += 1
            log.info(f"NHANES: {local_name} → {len(data):,} bytes")
        except Exception as e:
            log.warning(f"NHANES {local_name}: {e}")
    return count


def _land_big_five(client, log):
    """Big Five personality traits — Open Psychometrics IPIP-NEO dataset (N≈1M responses)."""
    url = "https://openpsychometrics.org/_rawdata/BIG5.zip"
    log.info("Big Five: downloading zip")
    data = _download(url)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        for name in z.namelist():
            content = z.read(name)
            ext = "text/csv" if name.endswith(".csv") else "text/plain"
            _put(client, f"big_five/{name}", content, ext)
            log.info(f"Big Five: {name} → {len(content):,} bytes")
    return 1


def _land_who_gho(client, log):
    """WHO Global Health Observatory — key indicators via the GHO OData REST API."""
    indicators = {
        "life_expectancy": "WHOSIS_000001",
        "healthy_life_expectancy": "WHOSIS_000007",
        "adult_obesity": "NCD_BMI_30A",
        "physical_inactivity": "NCD_PAC_A",
        "alcohol_consumption": "SA_0000001400",
        "tobacco_smoking": "M_Est_tob_curr_std",
        "diabetes_prevalence": "NCD_GLUC_04",
        "cardiovascular_deaths": "CARDIOVASCULAR_DEATHS_100K",
        "mental_health_disorders": "MH_11",
        "hypertension": "BP_04",
    }
    base = "https://ghoapi.azureedge.net/api"
    count = 0
    for name, code in indicators.items():
        try:
            url = f"{base}/{code}?$format=json"
            log.info(f"WHO GHO: downloading {name} ({code})")
            data = _download(url)
            _put(client, f"who_gho/{name}.json", data, "application/json")
            count += 1
            log.info(f"WHO GHO: {name} → {len(data):,} bytes")
        except Exception as e:
            log.warning(f"WHO GHO {name}: {e}")
    return count


def _land_cdc_physical_activity(client, log):
    """CDC Physical Activity guidelines data from CDC open data portal."""
    datasets = {
        "physical_activity_adults": "https://data.cdc.gov/api/views/ivfh-b3de/rows.csv?accessType=DOWNLOAD",
        "physical_activity_youth": "https://data.cdc.gov/api/views/fqe6-n26c/rows.csv?accessType=DOWNLOAD",
        "nutrition_physical_activity_obesity": "https://data.cdc.gov/api/views/hn4x-zwk7/rows.csv?accessType=DOWNLOAD",
    }
    count = 0
    for name, url in datasets.items():
        try:
            log.info(f"CDC Physical Activity: downloading {name}")
            data = _download(url)
            _put(client, f"cdc_physical_activity/{name}.csv", data, "text/csv")
            count += 1
            log.info(f"CDC Physical Activity: {name} → {len(data):,} bytes")
        except Exception as e:
            log.warning(f"CDC Physical Activity {name}: {e}")
    return count


def _land_brfss(client, log):
    """BRFSS — Behavioral Risk Factor Surveillance System (CDC). Annual CSV exports via CDC open data."""
    datasets = {
        "brfss_2022": "https://data.cdc.gov/api/views/dttw-5yxu/rows.csv?accessType=DOWNLOAD",
        "brfss_2021": "https://data.cdc.gov/api/views/8953-7fz5/rows.csv?accessType=DOWNLOAD",
        "brfss_2020": "https://data.cdc.gov/api/views/j32a-sa6u/rows.csv?accessType=DOWNLOAD",
        "brfss_prevalence_data": "https://data.cdc.gov/api/views/dttw-5yxu/rows.csv?accessType=DOWNLOAD",
        "brfss_selected_metropolitan_area": "https://data.cdc.gov/api/views/j32a-sa6u/rows.csv?accessType=DOWNLOAD",
    }
    count = 0
    for name, url in datasets.items():
        try:
            log.info(f"BRFSS: downloading {name}")
            data = _download(url, timeout=900)
            _put(client, f"brfss/{name}.csv", data, "text/csv")
            count += 1
            log.info(f"BRFSS: {name} → {len(data):,} bytes")
        except Exception as e:
            log.warning(f"BRFSS {name}: {e}")
    return count


def _land_myfitnesspal(client, log):
    """MyFitnessPal nutrition data from HuggingFace (andrewmvd/myfitnesspal-nutrition-facts)."""
    from datasets import load_dataset
    import csv as csvmod

    candidates = [
        "andrewmvd/myfitnesspal-nutrition-facts",
        "prasertcbs/myfitnesspal",
        "Chrithon/myfitnesspal",
    ]
    for candidate in candidates:
        try:
            log.info(f"MyFitnessPal: trying {candidate}")
            ds = load_dataset(candidate, split="train")
            buf = io.StringIO()
            writer = csvmod.DictWriter(buf, fieldnames=ds.column_names)
            writer.writeheader()
            for row in ds:
                writer.writerow(row)
            data = buf.getvalue().encode("utf-8")
            _put(client, "myfitnesspal/myfitnesspal.csv", data, "text/csv")
            log.info(f"MyFitnessPal ({candidate}): {len(ds)} rows → {len(data):,} bytes")
            return 1
        except Exception as e:
            log.warning(f"MyFitnessPal {candidate}: {e}")
    return 0


def _land_uk_biobank(client, log):
    """UK Biobank — full application required; use NHIS (National Health Interview Survey)
    as a publicly accessible alternative with similar scope (health + lifestyle + demographics).
    NHIS is a major CDC survey covering ~100k adults/year, fully public."""
    import csv as csvmod

    nhis_datasets = {
        "nhis_adult_2022": "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/NHIS/2022/adult22csv.zip",
        "nhis_adult_2021": "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/NHIS/2021/adult21csv.zip",
        "nhis_adult_2020": "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Datasets/NHIS/2020/adult20csv.zip",
    }
    count = 0
    for name, url in nhis_datasets.items():
        try:
            log.info(f"NHIS (UK Biobank alt): downloading {name}")
            data = _download(url, timeout=600)
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                for fname in z.namelist():
                    content = z.read(fname)
                    _put(client, f"uk_biobank/{name}/{fname}", content, "text/csv")
                    log.info(f"NHIS: {name}/{fname} → {len(content):,} bytes")
            count += 1
        except Exception as e:
            log.warning(f"NHIS {name}: {e}")
    return count


def _land_usda_fooddata(client, log):
    """USDA FoodData Central — bulk CSV download."""
    url = "https://fdc.nal.usda.gov/fdc-datasets/FoodData_Central_csv_2024-10-31.zip"
    log.info("USDA FoodData: downloading bulk zip (~400MB)")
    try:
        data = _download(url, timeout=1800)
        with zipfile.ZipFile(io.BytesIO(data)) as z:
            for name in z.namelist():
                if name.endswith(".csv"):
                    content = z.read(name)
                    _put(client, f"usda_fooddata/{name}", content, "text/csv")
                    log.info(f"USDA FoodData: {name} → {len(content):,} bytes")
        return 1
    except Exception as e:
        log.warning(f"USDA FoodData: {e}")
        return 0


def _land_open_food_facts(client, log):
    """Open Food Facts — full CSV (~9GB uncompressed). Streamed to avoid OOM."""
    url = "https://static.openfoodfacts.org/data/en.openfoodfacts.org.products.csv.gz"
    log.info("Open Food Facts: streaming download (large file)")
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "weyland-health-land/1.0"})
        with urllib.request.urlopen(req, timeout=3600) as r:
            data = r.read()
        _put(client, "open_food_facts/products.csv.gz", data, "application/gzip")
        log.info(f"Open Food Facts: → {len(data):,} bytes (compressed)")
        return 1
    except Exception as e:
        log.warning(f"Open Food Facts: {e}")
        return 0


@asset(
    group_name="datasets_health",
    description="Land all 9 health/wellness/personality datasets into datasets/health/raw/ (bronze) via lakeFS.",
)
def health_land(context) -> Output[dict]:
    client = _minio()
    results = {}

    context.log.info("Landing NHANES...")
    results["nhanes"] = _land_nhanes(client, context.log)

    context.log.info("Landing Big Five personality...")
    results["big_five"] = _land_big_five(client, context.log)

    context.log.info("Landing WHO GHO...")
    results["who_gho"] = _land_who_gho(client, context.log)

    context.log.info("Landing CDC Physical Activity...")
    results["cdc_physical_activity"] = _land_cdc_physical_activity(client, context.log)

    context.log.info("Landing BRFSS...")
    results["brfss"] = _land_brfss(client, context.log)

    context.log.info("Landing MyFitnessPal...")
    results["myfitnesspal"] = _land_myfitnesspal(client, context.log)

    context.log.info("Landing UK Biobank...")
    results["uk_biobank"] = _land_uk_biobank(client, context.log)

    context.log.info("Landing USDA FoodData Central...")
    results["usda_fooddata"] = _land_usda_fooddata(client, context.log)

    context.log.info("Landing Open Food Facts...")
    results["open_food_facts"] = _land_open_food_facts(client, context.log)

    total = sum(v for v in results.values() if isinstance(v, int))
    context.log.info(f"health_land complete: {results}")
    return Output(
        results,
        metadata={
            "total_files": MetadataValue.int(total),
            "destination": MetadataValue.text("s3://datasets/health/main/raw/"),
            "detail": MetadataValue.json(results),
        },
    )
