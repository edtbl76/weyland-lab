"""One-off — extract EXACT survey variable labels for the field-docs ingest (B80 / full codebook).

  NHANES: the .XPT (SAS transport) files embed variable labels → read them with pyreadstat.
  NHIS:   the CSVs carry no labels, but CDC ships SAS input statements with `label VAR = "text";` → fetch + parse.

Run in the dagster user-code pod (it has internet — that's how the data landed):
  kubectl -n weyland exec deploy/dagster-user-code -- sh -c 'pip install -q pyreadstat && python /app/scripts/extract_survey_labels.py'

Prints two Python dict literals (NHANES, NHIS) to paste into weyland_pipeline/datasets_field_docs.py.
"""
import re
import tempfile
import urllib.request

NHANES_URLS = [
    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DEMO_J.xpt",
    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BMX_J.xpt",
    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/BPX_J.xpt",
    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/TCHOL_J.xpt",
    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DIQ_J.xpt",
    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/PAQ_J.xpt",
    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DR1TOT_J.xpt",
    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/DPQ_J.xpt",
    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/WHQ_J.xpt",
    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2017/DataFiles/SLQ_J.xpt",
    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/DEMO_I.xpt",
    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/BMX_I.xpt",
    "https://wwwn.cdc.gov/Nchs/Data/Nhanes/Public/2015/DataFiles/PAQ_I.xpt",
]

# NHIS SAS input statements (label VAR = "…";). Candidate locations — the script tries each per year.
NHIS_SAS = {
    "2022": ["https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Program_Code/NHIS/2022/adult22.sas"],
    "2021": ["https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Program_Code/NHIS/2021/adult21.sas"],
    "2020": ["https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Program_Code/NHIS/2020/adult20.sas"],
}


def _get(url, timeout=180):
    req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
    return urllib.request.urlopen(req, timeout=timeout).read()


def nhanes_labels():
    import pyreadstat
    out = {}
    for url in NHANES_URLS:
        try:
            data = _get(url)
            with tempfile.NamedTemporaryFile(suffix=".xpt") as tf:
                tf.write(data)
                tf.flush()
                _df, meta = pyreadstat.read_xport(tf.name)
                for name, lab in zip(meta.column_names, meta.column_labels or []):
                    if lab and name:
                        out.setdefault(name.lower(), lab.strip())
        except Exception as e:  # noqa: BLE001
            print(f"# NHANES ERR {url}: {e}")
    return out


def nhis_labels():
    out = {}
    for year, urls in NHIS_SAS.items():
        for url in urls:
            try:
                txt = _get(url).decode("latin-1", "replace")
            except Exception as e:  # noqa: BLE001
                print(f"# NHIS ERR {url}: {e}")
                continue
            for var, lab in re.findall(r'label\s+(\w+)\s*=\s*"([^"]*)"', txt, re.IGNORECASE):
                out.setdefault(var.lower(), lab.strip())
            break
    return out


def _dump(name, d):
    print(f"{name} = {{")
    for k in sorted(d):
        v = d[k].replace('"', "'")
        print(f'    "{k}": "{v}",')
    print("}")


if __name__ == "__main__":
    nh = nhanes_labels()
    ni = nhis_labels()
    print(f"# NHANES: {len(nh)} labels  |  NHIS: {len(ni)} labels")
    _dump("NHANES", nh)
    _dump("NHIS", ni)
