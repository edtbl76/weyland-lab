"""WHO Global Health Observatory — 10 key indicators via the GHO OData REST API."""
from dagster import MetadataValue, Output, asset
from .health_common import health_minio, health_put, health_download, check_source_freshness

INDICATORS = {
    "life_expectancy":          "WHOSIS_000001",
    "healthy_life_expectancy":  "WHOSIS_000007",
    "adult_obesity":            "NCD_BMI_30A",
    "physical_inactivity":      "NCD_PAC_A",
    "alcohol_consumption":      "SA_0000001400",
    "tobacco_smoking":          "M_Est_tob_curr_std",
    "diabetes_prevalence":      "NCD_GLUC_04",
    "cardiovascular_deaths":    "CARDIOVASCULAR_DEATHS_100K",
    "mental_health_disorders":  "MH_11",
    "hypertension":             "BP_04",
}


@asset(group_name="datasets_health", description="Land WHO GHO indicators (JSON) → health/raw/who_gho/.")
def datasets_health_who_gho_land(context) -> Output[dict]:
    if check_source_freshness(context, f"https://ghoapi.azureedge.net/api/WHOSIS_000001?$format=json"):
        return Output({"skipped": True}, metadata={"skipped": MetadataValue.bool(True)})
    client = health_minio()
    out = {}
    for name, code in INDICATORS.items():
        try:
            url = f"https://ghoapi.azureedge.net/api/{code}?$format=json"
            data = health_download(url)
            health_put(client, f"who_gho/{name}.json", data, "application/json")
            out[name] = len(data)
            context.log.info(f"who_gho/{name}.json → {len(data):,} bytes")
        except Exception as e:
            out[name] = f"ERROR: {e}"
            context.log.warning(f"WHO GHO {name}: {e}")
    ok = sum(1 for v in out.values() if isinstance(v, int))
    return Output(out, metadata={"files": MetadataValue.int(ok), "detail": MetadataValue.json(out)})
