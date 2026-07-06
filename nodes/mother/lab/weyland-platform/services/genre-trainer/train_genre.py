#!/usr/bin/env python3
"""Genre-classifier trainer — the weyland platform's REMOTE training job.

Runs on rogueone (training COMPUTE — 128 GB / 32 cores / RTX 5000 Ada), NOT the weyland k3s cluster. Reads
spotify_tracks silver DIRECT from the lakeFS S3 gateway, trains a RandomForest genre classifier, and logs
params/metrics + the registered model to weyland MLflow.

Two modes:
  * default (single fit)  — one RandomForest, one MLflow run, model registered.
  * --tune (Ray Tune)     — a hyperparameter sweep on a local Ray cluster (rogueone's cores); every trial is its
                            own MLflow run (params/metrics), and the BEST config is retrained + registered.

The key design point — TWO MLflow planes:
  * metadata (params, metrics, registry entry) → the MLflow tracking server → Postgres. Small, always fine.
  * artifact (the model blob) → uploaded DIRECT to MinIO, because the experiment's artifact_location is
    s3://mlflow/… (not the mlflow-artifacts:/ proxy). This BYPASSES MLflow's --serve-artifacts relay, so a
    large model.pkl never has to squeeze through the 1Gi MLflow pod (which timed out relaying it).

Self-contained: no weyland_pipeline dependency. Creds (LAKEFS_* / AWS_*) and endpoints are supplied by
entrypoint.sh, which — given only a mounted kubeconfig — reads the Secrets (lakefs-creds, aidlc-kb-minio-secret)
and opens the mlflow/minio/lakefs port-forwards via kubectl. So this module stays pure training: it reads its
config from env (LAKEFS_ENDPOINT/…, MLFLOW_TRACKING_URI, MLFLOW_S3_ENDPOINT_URL/AWS_*). Nothing secret on the CLI.
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
        # NEXT ITERATION — features from Feast (get_historical_features, point-in-time). Same logging below;
        # only the feature retrieval changes. Hard stop (not a silent fallback) until wired.
        sys.exit("feast source not yet implemented — silver first to prove the path, feast next")
    sys.exit(f"unknown --source {source!r}")


def _prep(source: str):
    df = read_features(source)
    X, y = df[AUDIO].to_numpy(), df["track_genre"].to_numpy()
    n_classes = int(df["track_genre"].nunique())
    Xtr, Xte, ytr, yte = train_test_split(X, y, test_size=0.2, random_state=42, stratify=y)
    return (Xtr, Xte, ytr, yte), n_classes, len(df)


# --- mlflow ------------------------------------------------------------------------------------------------

def ensure_experiment(client: MlflowClient, name: str) -> None:
    """Guarantee the experiment writes artifacts DIRECT to MinIO (s3://), not through the serve-artifacts proxy.
    If it already exists with a proxy (non-s3) location, STOP with a clear message rather than silently uploading
    through the proxy (which times out on a big model)."""
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


def _register(clf, source, params, acc, f1, n_classes, n_rows, run_name, registered_model):
    """One MLflow run: log params + metrics + the fitted model (artifact DIRECT to MinIO) and register it."""
    with mlflow.start_run(run_name=run_name):
        mlflow.log_params({"model": "RandomForestClassifier", "feature_source": source, "n_features": len(AUDIO),
                           "n_classes": int(n_classes), "n_rows": int(n_rows), **params})
        mlflow.log_metrics({"accuracy": acc, "f1_macro": f1})
        t0 = time.time()
        mlflow.sklearn.log_model(clf, "model", registered_model_name=registered_model)
        log(f"model logged + registered as {registered_model!r} in {time.time() - t0:.1f}s "
            f"— acc={acc:.3f} f1_macro={f1:.3f}")


# --- single fit --------------------------------------------------------------------------------------------

def _single(args, splits, n_classes, n_rows):
    Xtr, Xte, ytr, yte = splits
    log(f"[{args.source}] training RandomForest ({args.n_estimators} trees, max_depth {args.max_depth}) on "
        f"{len(Xtr):,} rows × {len(AUDIO)} features, {n_classes} classes…")
    t0 = time.time()
    clf = RandomForestClassifier(n_estimators=args.n_estimators, max_depth=args.max_depth,
                                 random_state=42, n_jobs=-1).fit(Xtr, ytr)
    log(f"[{args.source}] fit complete in {time.time() - t0:.1f}s — scoring…")
    pred = clf.predict(Xte)
    acc, f1 = float(accuracy_score(yte, pred)), float(f1_score(yte, pred, average="macro"))
    log(f"[{args.source}] acc={acc:.3f} f1_macro={f1:.3f}")
    _register(clf, args.source, {"n_estimators": args.n_estimators, "max_depth": args.max_depth, "mode": "single"},
              acc, f1, n_classes, n_rows, f"genre-{args.source}", args.registered_model)


# --- ray tune sweep ----------------------------------------------------------------------------------------

def _tune(args, splits, n_classes, n_rows):
    """Ray Tune hyperparameter sweep on a local Ray cluster (rogueone's cores). Each trial trains an RF with a
    sampled config, logs its own MLflow run (params + metrics, no artifact), and reports f1_macro to Tune. The
    best config is then retrained on the full train split and registered — one heavyweight artifact, not N."""
    import ray
    from ray import train, tune

    Xtr, Xte, ytr, yte = splits
    # Two ways this runs: SUBMITTED to the persistent head (`ray job submit` sets RAY_ADDRESS) → connect to it and
    # let its SSO-gated dashboard (ray.weyland.lab) show the job; or STANDALONE in a local container (docker run)
    # → start a private cluster + dashboard. The local dashboard is unauth (Jobs API = RCE) so it must be
    # published loopback-only (`-p 127.0.0.1:8265:8265`), never the host's 0.0.0.0.
    if os.environ.get("RAY_ADDRESS"):
        ray.init(address="auto")
        where = "submitted to the Ray head"
    else:
        ray.init(include_dashboard=True, dashboard_host="0.0.0.0", ignore_reinit_error=True)
        where = "local cluster (dashboard http://localhost:8265, publish -p 127.0.0.1:8265:8265)"
    log(f"[tune] Ray up ({where}) — {int(ray.cluster_resources().get('CPU', 0))} CPUs. Sweeping {args.trials} "
        f"trials (4 CPUs each → ~8 concurrent), each its own MLflow run…")
    data_ref = ray.put((Xtr, Xte, ytr, yte))
    experiment, source, registered, trials_n, n_feat = (args.experiment, args.source,
                                                        args.registered_model, args.trials, len(AUDIO))
    # Endpoints + creds a WORKER task needs to reach MLflow + MinIO (both LAN-reachable now — see ray-head.yaml).
    # Captured from the head/driver env and shipped into the tasks (the external worker's own env has neither).
    # IGNORE_TLS: MinIO's LAN ingress serves the mkcert wildcard cert the worker's boto3 doesn't trust.
    wenv = {k: os.environ[k] for k in ("MLFLOW_TRACKING_URI", "MLFLOW_S3_ENDPOINT_URL",
                                       "AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY")}
    wenv["AWS_DEFAULT_REGION"] = os.environ.get("AWS_DEFAULT_REGION", "us-east-1")
    wenv["MLFLOW_S3_IGNORE_TLS"] = "true"
    _pk = ("n_estimators", "max_depth", "max_features", "min_samples_leaf")

    def trainable(config):
        import os as o
        import mlflow as m
        import ray as r
        from sklearn.ensemble import RandomForestClassifier as RF
        from sklearn.metrics import accuracy_score as acc_s, f1_score as f1_s
        o.environ.update(wenv)
        a_tr, a_te, y_tr, y_te = r.get(data_ref)
        clf = RF(random_state=42, n_jobs=4, **{k: config[k] for k in _pk}).fit(a_tr, y_tr)
        pred = clf.predict(a_te)
        acc, f1 = float(acc_s(y_te, pred)), float(f1_s(y_te, pred, average="macro"))
        try:                                             # each trial = its own MLflow run (params + metrics only)
            m.set_tracking_uri(wenv["MLFLOW_TRACKING_URI"])
            m.set_experiment(experiment)
            with m.start_run(run_name="tune-trial"):
                m.log_params({**{k: config[k] for k in _pk}, "feature_source": source, "mode": "ray-tune"})
                m.log_metrics({"accuracy": acc, "f1_macro": f1})
        except Exception as e:
            print(f"[trainable] mlflow log skipped: {e}", flush=True)
        train.report({"accuracy": acc, "f1_macro": f1})

    space = {                                        # bounded so 113-class forests stay memory-sane under a sweep
        "n_estimators": tune.choice([100, 200]),
        "max_depth": tune.choice([12, 16, 20]),
        "max_features": tune.choice(["sqrt", "log2"]),
        "min_samples_leaf": tune.choice([1, 2, 4]),
    }
    tuner = tune.Tuner(
        tune.with_resources(trainable, {"cpu": 4}),
        param_space=space,
        tune_config=tune.TuneConfig(num_samples=args.trials, metric="f1_macro", mode="max"),
    )
    best = tuner.fit().get_best_result(metric="f1_macro", mode="max")
    bc = best.config
    log(f"[tune] best f1_macro={best.metrics['f1_macro']:.3f} acc={best.metrics['accuracy']:.3f} — "
        f"n_estimators={bc['n_estimators']} max_depth={bc['max_depth']} max_features={bc['max_features']} "
        f"min_samples_leaf={bc['min_samples_leaf']}. Retraining the winner ON A WORKER + registering…")

    @ray.remote(num_cpus=4)
    def retrain_register(config):
        # Runs on a WORKER (rogueone) — it has the RAM for the full winning model and reaches MLflow+MinIO over the
        # LAN, so the head/driver never holds the multi-GB model (no head OOM — the exit-137 that hit before).
        import os as o
        import mlflow
        import mlflow.sklearn
        import ray as r
        from sklearn.ensemble import RandomForestClassifier as RF
        from sklearn.metrics import accuracy_score as acc_s, f1_score as f1_s
        o.environ.update(wenv)
        a_tr, a_te, y_tr, y_te = r.get(data_ref)
        clf = RF(random_state=42, n_jobs=-1, **{k: config[k] for k in _pk}).fit(a_tr, y_tr)
        pred = clf.predict(a_te)
        acc, f1 = float(acc_s(y_te, pred)), float(f1_s(y_te, pred, average="macro"))
        mlflow.set_tracking_uri(wenv["MLFLOW_TRACKING_URI"])
        mlflow.set_experiment(experiment)
        with mlflow.start_run(run_name=f"genre-{source}-tuned"):
            mlflow.log_params({"model": "RandomForestClassifier", "feature_source": source, "n_features": n_feat,
                               "n_classes": int(n_classes), "n_rows": int(n_rows), "mode": "ray-tune-best",
                               "tune_trials": trials_n, **{k: config[k] for k in _pk}})
            mlflow.log_metrics({"accuracy": acc, "f1_macro": f1})
            mlflow.sklearn.log_model(clf, "model", registered_model_name=registered)
        return acc, f1

    acc, f1 = ray.get(retrain_register.remote(bc))
    log(f"winner registered as {registered!r} (retrained on a worker) — acc={acc:.3f} f1_macro={f1:.3f}")
    ray.shutdown()


def _envflag(name):
    return os.environ.get(name, "").lower() in ("1", "true", "yes")


def main():
    ap = argparse.ArgumentParser(description="Remote genre-classifier trainer → weyland MLflow")
    ap.add_argument("--source", default=os.environ.get("SOURCE", "silver"), choices=["silver", "feast"])
    ap.add_argument("--n-estimators", type=int, default=int(os.environ.get("N_ESTIMATORS", "100")))
    ap.add_argument("--max-depth", type=int, default=int(os.environ.get("MAX_DEPTH", "20")))
    ap.add_argument("--experiment", default=os.environ.get("EXPERIMENT", "genre-classifier"))
    ap.add_argument("--registered-model", default=os.environ.get("REGISTERED_MODEL", "genre_classifier"))
    ap.add_argument("--tune", action="store_true", default=_envflag("TUNE"),
                    help="Ray Tune hyperparameter sweep (local Ray cluster) instead of a single fit")
    ap.add_argument("--trials", type=int, default=int(os.environ.get("TRIALS", "24")))
    args = ap.parse_args()

    splits, n_classes, n_rows = _prep(args.source)
    mlflow.set_tracking_uri(os.environ["MLFLOW_TRACKING_URI"])
    ensure_experiment(MlflowClient(), args.experiment)
    mlflow.set_experiment(args.experiment)
    log(f"logging to MLflow ({os.environ['MLFLOW_TRACKING_URI']}) — artifacts DIRECT to MinIO"
        f"{' — Ray Tune mode' if args.tune else ''}…")
    (_tune if args.tune else _single)(args, splits, n_classes, n_rows)
    log("done.")


if __name__ == "__main__":
    main()
