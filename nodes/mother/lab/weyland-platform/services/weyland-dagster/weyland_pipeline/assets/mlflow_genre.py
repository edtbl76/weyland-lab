"""MLflow training assets (grid MLflow — "experiment tracking") — a genre classifier over Spotify audio
features, trained TWO ways to demonstrate three documentable use cases:

  1. the ML task itself — audio features (danceability … tempo) → track_genre (a real classification problem);
  2. FEAST as the feature source — get_historical_features → train (the Feast *consumer*, point-in-time serving);
  3. training DIRECTLY on the lakehouse silver Parquet — no feature store, straight from the lake.

Both log to the SAME MLflow experiment (`genre-classifier`) tagged by `feature_source`, and both register the
model (`genre_classifier`) — so the two sourcing paths are directly comparable in the MLflow UI. Same task, two
architectures: the docs contrast when Feast (point-in-time / serving consistency) vs silver-direct (simple
batch) is the right call. See docs/runbooks/mlflow-training.md."""
import os
import tempfile

import pandas as pd
from dagster import MetadataValue, Output, asset

from .datasets_lib import io

_AUDIO = ["danceability", "energy", "key", "loudness", "mode", "speechiness",
          "acousticness", "instrumentalness", "liveness", "valence", "tempo"]
_MLFLOW = os.environ.get("MLFLOW_TRACKING_URI", "http://mlflow.weyland.svc.cluster.local:5000")


def _read_spotify(mc, log):
    log.info("reading spotify_tracks silver from lakeFS…")
    frames = []
    for obj in mc.list_objects("music", prefix=f"{io.branch()}/parquet/spotify_tracks/", recursive=True):
        if not obj.object_name.endswith(".parquet"):
            continue
        t = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False)
        t.close()
        try:
            mc.fget_object("music", obj.object_name, t.name)
            frames.append(pd.read_parquet(t.name))
        finally:
            os.unlink(t.name)
    df = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
    df["track_id"] = df["track_id"].astype(str)
    for c in _AUDIO:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["track_id", "track_genre"] + _AUDIO).drop_duplicates("track_id")
    # drop ultra-rare genres so stratified split + per-class metrics are well-defined
    keep = df["track_genre"].value_counts()
    df = df[df["track_genre"].isin(keep[keep >= 20].index)]
    log.info(f"spotify silver: {len(df):,} rows / {df['track_genre'].nunique()} genres after cleaning")
    return df


def _train_and_log(df, source, log) -> dict:
    import mlflow
    import mlflow.sklearn
    from sklearn.ensemble import RandomForestClassifier
    from sklearn.metrics import accuracy_score, f1_score
    from sklearn.model_selection import train_test_split

    X, y = df[_AUDIO].to_numpy(), df["track_genre"].to_numpy()
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    mlflow.set_tracking_uri(_MLFLOW)
    mlflow.set_experiment("genre-classifier")
    log.info(f"[{source}] training RandomForest (200 trees) on {len(Xtr):,} rows × {len(_AUDIO)} features, "
             f"{df['track_genre'].nunique()} classes — verbose, watch stdout for per-tree progress…")
    with mlflow.start_run(run_name=f"genre-{source}"):
        # verbose=2 → sklearn prints per-tree build progress to stdout (Dagster compute logs) so a long fit
        # narrates itself instead of showing "Started" in silence.
        clf = RandomForestClassifier(n_estimators=200, random_state=42, n_jobs=-1, verbose=2).fit(Xtr, ytr)
        log.info(f"[{source}] fit complete — scoring + logging the model to MLflow…")
        pred = clf.predict(Xte)
        acc, f1 = float(accuracy_score(yte, pred)), float(f1_score(yte, pred, average="macro"))
        mlflow.log_params({"model": "RandomForestClassifier", "n_estimators": 200, "feature_source": source,
                           "n_features": len(_AUDIO), "n_classes": int(df["track_genre"].nunique()), "n_rows": len(df)})
        mlflow.log_metrics({"accuracy": acc, "f1_macro": f1})
        mlflow.sklearn.log_model(clf, "model", registered_model_name="genre_classifier")
    log.info(f"genre-{source}: acc={acc:.3f} f1={f1:.3f} over {df['track_genre'].nunique()} genres, {len(df)} rows")
    return {"source": source, "accuracy": acc, "f1_macro": f1,
            "n_classes": int(df["track_genre"].nunique()), "n_rows": len(df)}


def _meta(out):
    return {k: (MetadataValue.float(v) if isinstance(v, float) else MetadataValue.int(v))
            for k, v in out.items() if k != "source"}


@asset(group_name="datasets_music_ml",
       description="USE CASE 3 — train the genre classifier DIRECTLY on the lakehouse silver Parquet (no feature "
                   "store). Tracked + registered in MLflow (experiment genre-classifier, feature_source=silver).")
def mlflow_genre_from_silver(context):
    out = _train_and_log(_read_spotify(io.client(), context.log), "silver", context.log)
    return Output(out, metadata=_meta(out))


@asset(group_name="datasets_music_ml",
       description="USE CASE 2 — train the SAME classifier but source the audio features from FEAST "
                   "(get_historical_features — the Feast consumer / point-in-time retrieval). Tracked in MLflow.")
def mlflow_genre_from_feast(context):
    from feast import FeatureStore

    labels = _read_spotify(io.client(), context.log)[["track_id", "track_genre"]]
    fs = FeatureStore(repo_path="/app/feast_repo")
    edf = pd.DataFrame({"track_id": labels["track_id"], "event_timestamp": pd.Timestamp("2024-01-01", tz="UTC")})
    context.log.info(f"Feast get_historical_features — point-in-time join over {len(edf):,} track entities. "
                     "THIS IS THE SLOW STEP (no per-row progress from Feast); expect several minutes at scale…")
    feats = fs.get_historical_features(
        entity_df=edf, features=[f"track_audio_features:{c}" for c in _AUDIO]).to_df()
    context.log.info(f"Feast returned {len(feats):,} feature rows — merging labels + training…")
    df = feats.merge(labels, on="track_id").dropna(subset=_AUDIO + ["track_genre"])
    out = _train_and_log(df, "feast", context.log)
    return Output(out, metadata=_meta(out))
