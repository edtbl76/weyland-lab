"""Feast training-set retrieval (grid Feast — the point-in-time CONSUMER, UC2).

Builds the genre-classifier's training set *from Feast*: an entity_df of every spotify `track_id` (+ the
`track_genre` label from silver) → `FeatureStore.get_historical_features` (a point-in-time join over the
`track_audio_features` view, whose offline store is the STRICT-mTLS `feast` Postgres DB) → written to lakeFS as
parquet.

**Why this is an in-cluster, MESHED asset and not part of the trainer:** `get_historical_features` connects
straight to the offline Postgres store (psycopg3), and that store is STRICT mTLS — only a mesh member can reach
it. The remote trainer runs on rogueone (external) and the Ray head is `hostNetwork` (no sidecar); neither can do
the join. So the point-in-time retrieval runs here (Dagster is meshed + already carries `feast_repo/`) and lands
the result in lakeFS. The external trainer then reads it via `--source feast` and fits it *exactly* as it fits
`--source silver` — so the ONLY difference between the two paths is where the features came from (silver-direct vs
Feast point-in-time), which is the UC2/UC3 contrast the docs draw.

Supersedes the in-cluster `mlflow_genre_from_{silver,feast}` assets (training moved to rogueone; those OOM'd the
1Gi pod + timed the artifact upload out through the serve-artifacts proxy).

See docs/runbooks/mlflow-training.md (UC2) + docs/runbooks/remote-training.md."""
import io as _bio
import os
import tempfile

import pandas as pd
import pyarrow as pa
import pyarrow.parquet as pq
from dagster import MetadataValue, Output, asset

from .datasets_lib import io

_AUDIO = ["danceability", "energy", "key", "loudness", "mode", "speechiness",
          "acousticness", "instrumentalness", "liveness", "valence", "tempo"]
_REPO = "music"
_DATASET = "genre_feast_training"   # the trainer reads music/<branch>/parquet/genre_feast_training/


def _read_spotify_labels(mc, log) -> pd.DataFrame:
    """Entity keys + labels from silver: track_id → track_genre (the same cleaning the trainer applies to silver,
    so the two paths select the same tracks). Only the two columns are read — the features come from Feast."""
    log.info("reading spotify_tracks silver from lakeFS (track_id + track_genre)…")
    frames = []
    for obj in mc.list_objects(_REPO, prefix=f"{io.branch()}/parquet/spotify_tracks/", recursive=True):
        if not obj.object_name.endswith(".parquet"):
            continue
        t = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
        t.close()
        try:
            mc.fget_object(_REPO, obj.object_name, t.name)
            frames.append(pd.read_parquet(t.name, columns=["track_id", "track_genre"]))
        finally:
            os.unlink(t.name)
    df = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
    df["track_id"] = df["track_id"].astype(str)
    df = df.dropna(subset=["track_id", "track_genre"]).drop_duplicates("track_id")
    keep = df["track_genre"].value_counts()          # drop ultra-rare genres → well-defined stratified split
    df = df[df["track_genre"].isin(keep[keep >= 20].index)]
    log.info(f"spotify labels: {len(df):,} tracks / {df['track_genre'].nunique()} genres after cleaning")
    return df[["track_id", "track_genre"]]


@asset(group_name="datasets_music_ml",
       description="Feast CONSUMER (UC2): build the genre-classifier training set via Feast "
                   "get_historical_features (point-in-time join over track_audio_features; offline store = the "
                   "STRICT-mTLS feast Postgres) → lakeFS music/parquet/genre_feast_training/. Runs MESHED "
                   "in-cluster (only a mesh member reaches the offline store); the external rogueone trainer then "
                   "fits it via --source feast. Supersedes the old in-cluster mlflow_genre_from_* assets.")
def genre_feast_training_set(context):
    from feast import FeatureStore

    mc = io.client()
    labels = _read_spotify_labels(mc, context.log)
    fs = FeatureStore(repo_path=os.environ.get("FEAST_REPO", "/app/feast_repo"))
    # track_audio_features is static (synthetic event_timestamp) → any as-of time returns the one value per track;
    # the point-in-time machinery is exercised, it just doesn't bite for a static feature (state_health_risk is
    # where time-travel actually matters — a future second consumer).
    edf = pd.DataFrame({"track_id": labels["track_id"],
                        "event_timestamp": pd.Timestamp("2024-01-01", tz="UTC")})
    context.log.info(f"Feast get_historical_features — point-in-time join over {len(edf):,} track entities "
                     "(the SLOW step; Feast emits no per-row progress; minutes at scale)…")
    feats = fs.get_historical_features(
        entity_df=edf, features=[f"track_audio_features:{c}" for c in _AUDIO]).to_df()
    feats["track_id"] = feats["track_id"].astype(str)
    for c in _AUDIO:
        feats[c] = pd.to_numeric(feats[c], errors="coerce")
    df = (feats.merge(labels, on="track_id")
                .dropna(subset=_AUDIO + ["track_genre"])
                .drop_duplicates("track_id"))[["track_id", *_AUDIO, "track_genre"]]
    context.log.info(f"Feast returned {len(feats):,} feature rows → {len(df):,} training rows after label merge")

    # write parquet THROUGH the lakeFS gateway, then commit (one version per run — the silver-broker pattern)
    buf = _bio.BytesIO()
    pq.write_table(pa.Table.from_pandas(df, preserve_index=False), buf)
    io.put(mc, _REPO, f"parquet/{_DATASET}/part.parquet", buf.getvalue())

    import lakefs

    lc = lakefs.Client(host=io.endpoint(), username=os.environ["LAKEFS_ACCESS_KEY_ID"],
                       password=os.environ["LAKEFS_SECRET_ACCESS_KEY"])
    br = lakefs.Repository(_REPO, client=lc).branch(io.branch())
    committed, cid = False, ""
    if list(br.uncommitted()):
        ref = br.commit(message="genre_feast_training_set (Feast point-in-time retrieval)",
                        metadata={"producer": "dagster:genre_feast_training_set"})
        cid = ref.get_commit().id
        committed = True
        context.log.info(f"lakeFS {_REPO}/{io.branch()}: committed → {cid[:12]}")
    else:
        context.log.info(f"lakeFS {_REPO}/{io.branch()}: no change to commit")

    out = {"rows": len(df), "genres": int(df["track_genre"].nunique()),
           "path": f"lakefs://{_REPO}/{io.branch()}/parquet/{_DATASET}/", "committed": committed}
    return Output(out, metadata={"rows": MetadataValue.int(out["rows"]),
                                 "genres": MetadataValue.int(out["genres"]),
                                 "path": MetadataValue.text(out["path"]),
                                 "commit": MetadataValue.text(cid or "—")})
