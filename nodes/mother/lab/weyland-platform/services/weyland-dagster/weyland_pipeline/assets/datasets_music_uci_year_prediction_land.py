"""Million Song Dataset (MSD) — UCI YearPredictionMSD subset (515k songs, 90 audio features).

Full MSD (1M songs) requires the AWS public dataset snapshot (~300GB) or a university data
sharing agreement (Drexel, Ithaca, QMUL, NYU, UCSD, UPF have copies). See backlog B76 for
the AWS snapshot workflow.

This asset uses the UCI YearPredictionMSD subset — 515k songs, 90 timbre/loudness features
from the MSD, originally used for year-of-release prediction. Metadata-only (no audio),
but covers the same audio feature space as the full MSD.
Source: https://archive.ics.uci.edu/ml/machine-learning-databases/00203/YearPredictionMSD.txt.zip
"""
import io
import zipfile
from dagster import MetadataValue, Output, asset
from .music_common import music_minio, music_put, music_download

UCI_MSD_URL = "https://archive.ics.uci.edu/ml/machine-learning-databases/00203/YearPredictionMSD.txt.zip"

COLUMN_NAMES = (
    ["year"] +
    [f"timbre_avg_{i}" for i in range(12)] +
    [f"timbre_cov_{i}" for i in range(78)]
)


@asset(group_name="datasets_music", description="Land MSD UCI subset (515k songs, 90 audio features) → music/raw/uci_year_prediction/.")
def datasets_music_uci_year_prediction_land(context) -> Output[dict]:
    client = music_minio()
    context.log.info("MSD UCI subset: downloading YearPredictionMSD.txt.zip (~200MB)")
    data = music_download(UCI_MSD_URL, timeout=600)
    with zipfile.ZipFile(io.BytesIO(data)) as z:
        fname = next(n for n in z.namelist() if n.endswith(".txt"))
        content = z.read(fname)

    # Add header row — file has no column names
    header = ",".join(COLUMN_NAMES) + "\n"
    csv_data = header.encode("utf-8") + content
    music_put(client, "uci_year_prediction/uci_year_prediction.csv", csv_data, "text/csv")
    rows = content.count(b"\n")
    context.log.info(f"uci_year_prediction/uci_year_prediction.csv: {rows:,} rows → {len(csv_data):,} bytes")
    return Output({"rows": rows, "source": "UCI YearPredictionMSD"}, metadata={"rows": MetadataValue.int(rows)})
