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

# NHIS has no machine-readable input program — labels live in the PDF codebook. Each variable is a block:
#   Variable: <NAME> … Description: <label> … Recode:  → parse that out.
NHIS_CODEBOOK = "https://ftp.cdc.gov/pub/Health_Statistics/NCHS/Dataset_Documentation/NHIS/2022/Adult-nofreq-codebook.pdf"


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
    import io

    import pypdf
    out = {}
    try:
        reader = pypdf.PdfReader(io.BytesIO(_get(NHIS_CODEBOOK, timeout=600)))
        text = "\n".join((p.extract_text() or "") for p in reader.pages)
    except Exception as e:  # noqa: BLE001
        print(f"# NHIS ERR {NHIS_CODEBOOK}: {e}")
        return out
    # 1) primary — the compact summary line above each value table: "NAME   <label>\nCode  Description"
    for m in re.finditer(r"\n([A-Za-z][\w]*)\s{2,}(.+?)\s*\n\s*Code\s+Description", text):
        lab = " ".join(m.group(2).split())
        if lab:
            out.setdefault(m.group(1).lower(), lab)
    # 2) fallback — the block's Description field (skip "Universe Description:")
    for m in re.finditer(r"Variable:\s*(\S+)(.*?)(?=Variable:|\Z)", text, re.DOTALL):
        var = m.group(1).lower()
        if var in out:
            continue
        dm = re.search(r"(?<!Universe )Description:\s*(.+?)\s*Recode:", m.group(2), re.DOTALL)
        if dm:
            lab = " ".join(dm.group(1).split())
            if lab:
                out.setdefault(var, lab)
    return out


def _dump(name, d):
    print(f"{name} = {{")
    for k in sorted(d):
        v = d[k].replace('"', "'")
        print(f'    "{k}": "{v}",')
    print("}")


if __name__ == "__main__":
    import sys
    only = sys.argv[1].lower() if len(sys.argv) > 1 else ""  # "" = both, "nhis" / "nhanes" = one
    if only != "nhis":
        nh = nhanes_labels()
        print(f"# NHANES: {len(nh)} labels")
        _dump("NHANES", nh)
    if only != "nhanes":
        ni = nhis_labels()
        print(f"# NHIS: {len(ni)} labels")
        _dump("NHIS", ni)
