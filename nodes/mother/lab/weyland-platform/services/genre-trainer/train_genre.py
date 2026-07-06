#!/usr/bin/env python3
"""Genre-classifier trainer — the weyland platform's REMOTE training job.

Runs on rogueone (training COMPUTE), NOT on the weyland k3s cluster. Reads spotify_tracks silver DIRECT from
the lakeFS S3 gateway, trains a RandomForest genre classifier, and logs params/metrics + the registered model
to the weyland MLflow server.

The key design point — TWO MLflow planes:
  * metadata (params, metrics, registry entry) → the MLflow tracking server → Postgres. Small, always fine.
  * artifact (the model blob) → uploaded DIRECT to MinIO, because the experiment's artifact_location is
    s3://mlflow/… (not the mlflow-artifacts:/ proxy). This BYPASSES MLflow's --serve-artifacts relay, so a
    large model.pkl never has to squeeze through the 1Gi MLflow pod (which timed out relaying it).

Self-contained: no weyland_pipeline dependency (that's why it re-implements the silver read). Config is entirely
via env so the same image runs anywhere it can reach the three endpoints (see README.md):
  LAKEFS_ENDPOINT / LAKEFS_ACCESS_KEY_ID / LAKEFS_SECRET_ACCESS_KEY / LAKEFS_BRANCH   — silver read (lakeFS gw)
  MLFLOW_TRACKING_URI                                                                  — tracking + registry
  MLFLOW_S3_ENDPOINT_URL / AWS_ACCESS_KEY_ID / AWS_SECRET_ACCESS_KEY                    — direct artifact write

Creds (LAKEFS_* / AWS_*) and endpoints are supplied by entrypoint.sh, which — given only a mounted kubeconfig —
reads the Secrets (lakefs-creds, aidlc-kb-minio-secret) and opens the mlflow/minio/lakefs port-forwards, both via
kubectl. So this module stays pure training: it just reads its config from env. Nothing secret touches the CLI.
"""
import argparse
import os
import sys
import tempfile
import time

import mlflow
import mlflow.sklearn
import pandas as pd
from minio import Minio
from mlflow.tracking import MlflowClient
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score
from sklearn.model_selection import train_test_split

AUDIO = ["danceability", "energy", "key", "loudness", "mode", "speechiness",
         "acousticness", "instrumentalness", "liveness", "valence", "tempo"]


def log(msg):
    print(f"[trainer] {msg}", flush=True)


# --- feature sources ---------------------------------------------------------------------------------------

def _lakefs_client() -> Minio:
    ep = os.environ.get("LAKEFS_ENDPOINT", "http://localhost:8000")
    return Minio(ep.replace("https://", "").replace("http://", ""),
                 access_key=os.environ["LAKEFS_ACCESS_KEY_ID"],
                 secret_key=os.environ["LAKEFS_SECRET_ACCESS_KEY"],
                 secure=ep.startswith("https://"))


def _read_spotify_silver() -> pd.DataFrame:
    branch = os.environ.get("LAKEFS_BRANCH", "main")
    mc = _lakefs_client()
    log(f"reading spotify_tracks silver from lakeFS ({branch}/parquet/spotify_tracks/)…")
    frames = []
    for obj in mc.list_objects("music", prefix=f"{branch}/parquet/spotify_tracks/", recursive=True):
        if not obj.object_name.endswith(".parquet"):
            continue
        t = tempfile.NamedTemporaryFile(suffix=".parquet", delete=False); t.close()
        try:
            mc.fget_object("music", obj.object_name, t.name)
            frames.append(pd.read_parquet(t.name))
        finally:
            os.unlink(t.name)
    df = pd.concat(frames, ignore_index=True) if len(frames) > 1 else frames[0]
    df["track_id"] = df["track_id"].astype(str)
    for c in AUDIO:
        df[c] = pd.to_numeric(df[c], errors="coerce")
    df = df.dropna(subset=["track_id", "track_genre"] + AUDIO).drop_duplicates("track_id")
    keep = df["track_genre"].value_counts()          # drop ultra-rare genres → well-defined stratified split
    df = df[df["track_genre"].isin(keep[keep >= 20].index)]
    log(f"spotify silver: {len(df):,} rows / {df['track_genre'].nunique()} genres after cleaning")
    return df


def read_features(source: str) -> pd.DataFrame:
    if source == "silver":
        return _read_spotify_silver()
    if source == "feast":
        # NEXT ITERATION — source features from Feast (get_historical_features, point-in-time). Needs the feast
        # repo baked in + reach to Postgres (offline) + Valkey (online). The MLflow logging below is identical;
        # only the feature retrieval changes. Keeping it a hard stop (not a silent fallback) until wired.
        sys.exit("feast source not yet implemented — silver first to prove the remote-training path, feast next")
    sys.exit(f"unknown --source {source!r}")


# --- mlflow ------------------------------------------------------------------------------------------------

def ensure_experiment(client: MlflowClient, name: str) -> None:
    """Guarantee the experiment writes artifacts DIRECT to MinIO (s3://), not through the serve-artifacts proxy.
    If it already exists with a proxy (non-s3) location — e.g. the old polluted experiment from the in-cluster
    attempts — STOP with a clear message instead of silently uploading through the proxy (which times out)."""
    loc = os.environ.get("MLFLOW_ARTIFACT_LOCATION", f"s3://mlflow/{name}")
    exp = client.get_experiment_by_name(name)
    if exp is None:
        client.create_experiment(name, artifact_location=loc)
        log(f"created experiment {name!r} → artifacts at {loc}")
    elif not exp.artifact_location.startswith("s3://"):
        sys.exit(f"experiment {name!r} exists with a PROXY artifact_location ({exp.artifact_location!r}). Purge "
                 f"it (mlflow gc on the server) so it's recreated with a direct s3:// location — see README.md.")
    else:
        log(f"experiment {name!r} → artifacts at {exp.artifact_location}")


def main():
    ap = argparse.ArgumentParser(description="Remote genre-classifier trainer → weyland MLflow")
    ap.add_argument("--source", default=os.environ.get("SOURCE", "silver"), choices=["silver", "feast"])
    ap.add_argument("--n-estimators", type=int, default=int(os.environ.get("N_ESTIMATORS", "100")))
    ap.add_argument("--max-depth", type=int, default=int(os.environ.get("MAX_DEPTH", "20")))
    ap.add_argument("--experiment", default=os.environ.get("EXPERIMENT", "genre-classifier"))
    ap.add_argument("--registered-model", default=os.environ.get("REGISTERED_MODEL", "genre_classifier"))
    args = ap.parse_args()

    df = read_features(args.source)
    X, y = df[AUDIO].to_numpy(), df["track_genre"].to_numpy()
    n_classes = df["track_genre"].nunique()
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)

    log(f"[{args.source}] training RandomForest ({args.n_estimators} trees, max_depth {args.max_depth}) on "
        f"{len(Xtr):,} rows × {len(AUDIO)} features, {n_classes} classes…")
    t0 = time.time()
    clf = RandomForestClassifier(n_estimators=args.n_estimators, max_depth=args.max_depth,
                                 random_state=42, n_jobs=-1, verbose=1).fit(Xtr, ytr)
    log(f"[{args.source}] fit complete in {time.time() - t0:.1f}s — scoring…")
    pred = clf.predict(Xte)
    acc, f1 = float(accuracy_score(yte, pred)), float(f1_score(yte, pred, average="macro"))
    log(f"[{args.source}] acc={acc:.3f} f1_macro={f1:.3f}")

    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    client = MlflowClient()
    ensure_experiment(client, args.experiment)
    mlflow.set_experiment(args.experiment)
    log(f"logging to MLflow ({os.environ['MLFLOW_TRACKING_URI']}) — artifact uploads DIRECT to MinIO…")
    with mlflow.start_run(run_name=f"genre-{args.source}"):
        mlflow.log_params({"model": "RandomForestClassifier", "n_estimators": args.n_estimators,
                           "max_depth": args.max_depth, "feature_source": args.source,
                           "n_features": len(AUDIO), "n_classes": int(n_classes), "n_rows": int(len(df))})
        mlflow.log_metrics({"accuracy": acc, "f1_macro": f1})
        t0 = time.time()
        mlflow.sklearn.log_model(clf, "model", registered_model_name=args.registered_model)
        log(f"model logged + registered as {args.registered_model!r} in {time.time() - t0:.1f}s")
    log("done.")


if __name__ == "__main__":
    main()
