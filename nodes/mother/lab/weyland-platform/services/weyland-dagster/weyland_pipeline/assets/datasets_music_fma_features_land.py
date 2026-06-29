"""FMA Features — 518 audio features per track (MFCCs, spectral, chroma, etc.).
Part of the FMA metadata zip; skipped in the original land due to size (~1GB uncompressed).
Added now to support audio feature ML workflows (Feast, Qdrant/Weaviate embeddings, ClickHouse OLAP)."""
import io
import os
import urllib.request
import zipfile

import pandas as pd
import numpy as np

from dagster import MetadataValue, Output, asset
from .music_common import music_minio, music_put

FMA_METADATA_URL = "https://os.unil.cloud.switch.ch/fma/fma_metadata.zip"
_FMA_ZIP = "/tmp/fma_metadata.zip"


@asset(group_name="datasets_music", description="Land FMA 518 audio features CSV → music/raw/fma_features/.")
def datasets_music_fma_features_land(context) -> Output[dict]:
    client = music_minio()
    if not os.path.exists(_FMA_ZIP):
        context.log.info("FMA Features: downloading metadata zip (~342MB)")
        urllib.request.urlretrieve(FMA_METADATA_URL, _FMA_ZIP)
    else:
        context.log.info("FMA Features: using cached metadata zip")

    with zipfile.ZipFile(_FMA_ZIP) as z:
        name = next(n for n in z.namelist() if n.endswith("features.csv"))
        context.log.info(f"FMA Features: extracting {name}")
        with z.open(name) as f:
            # features.csv has 3 header rows (feature family, name, statistics)
            df = pd.read_csv(f, index_col=0, header=[0, 1, 2], low_memory=False)

    # Flatten MultiIndex columns
    df.columns = ["_".join(str(x) for x in col if str(x) and not str(x).startswith("Unnamed"))
                  for col in df.columns]
    df = df.reset_index().replace({np.nan: None})
    data = df.to_csv(index=False).encode("utf-8")
    music_put(client, "fma_features/fma_features.csv", data, "text/csv")
    context.log.info(f"fma_features/fma_features.csv: {len(df):,} rows × {len(df.columns)} cols → {len(data):,} bytes")
    return Output({"rows": len(df), "cols": len(df.columns)}, metadata={"rows": MetadataValue.int(len(df))})
